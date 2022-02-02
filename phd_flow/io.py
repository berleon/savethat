from __future__ import annotations

import abc
import contextlib
import dataclasses
import os
import shutil
import sys
import time
from pathlib import Path
from typing import IO, Iterator, Optional, TypeVar, Union

import b2sdk.v2 as b2_api
from loguru import logger

from phd_flow import config as config_mod

T = TypeVar("T")
REMOTE_FILE = TypeVar("REMOTE_FILE")

PATH_LIKE = Union[str, Path]


class Storage(metaclass=abc.ABCMeta):
    @abc.abstractproperty
    def storage_path(self) -> Path:
        """The path to the local storage."""

    def __truediv__(self, key: PATH_LIKE) -> Path:
        """Shortcut to get the local path of the `key`.

        Equivalent to `storage.storage_path / key`."""
        return self.storage_path / key

    @abc.abstractmethod
    @contextlib.contextmanager
    def open(self, key: PATH_LIKE, mode: str = "r") -> Iterator[IO]:
        """Opens the file. Creates any none existing directories."""

    @abc.abstractmethod
    def upload(self, key: PATH_LIKE) -> str:
        """Uploads the directory referred to by `key`.

        `key` must reference a directory.
        """

    @abc.abstractmethod
    def download(self, key: PATH_LIKE) -> Path:
        """Downloads the directory referred to by `key`.

        `key` must reference a directory.
        """

    @abc.abstractmethod
    def download_file(self, key: PATH_LIKE) -> None:
        """Downloads the file given by `key`."""

    @abc.abstractmethod
    def remote_ls(
        self, key: PATH_LIKE = "", recursive: bool = False
    ) -> Iterator[Path]:
        """Returns a list of all remote directories.

        Args:
            key: the path to list remotely.
            recursive: if true, list the directory recursive.
        """

    @abc.abstractmethod
    def remove(
        self, key: PATH_LIKE, local: bool = True, remote: bool = False
    ) -> Iterator[Path]:
        """Removes the `key` locally or remotely.

        Use with care, this will also delete any subdirectories.
        It is not allowed to remove a `key` only on the remote.

        Args:
            key: key to remove
            local: remove the key locally
            remote: remove the key on the cloud storage
        """


class _SimulatedB2API:
    def __init__(self):
        self.account_info = b2_api.InMemoryAccountInfo()
        self.cache = b2_api.InMemoryCache()
        self.api = b2_api.B2Api(
            self.account_info,
            self.cache,
            api_config=b2_api.B2HttpApiConfig(
                _raw_api_class=b2_api.RawSimulator
            ),
        )
        self.raw_api = self.api.session.raw_api
        (
            self.application_key_id,
            self.master_key,
        ) = self.raw_api.create_account()
        self.api.authorize_account(
            "production", self.application_key_id, self.master_key
        )
        self.bucket_name = "test-bucket"
        self.bucket = self.api.create_bucket(self.bucket_name, "allPrivate")


@dataclasses.dataclass
class B2Storage(Storage):
    local_path: Path
    remote_path: Path
    b2_bucket: str
    b2_key_id: str
    b2_key: str
    _bucket: Optional[b2_api.Bucket] = None

    def __post_init__(self):
        if self._bucket is None:
            self._bucket = self._connect_b2()

    @staticmethod
    def from_file(config_file: PATH_LIKE) -> B2Storage:
        logger.info(
            f"Loading config from file: {str(config_file)}",
            file=str(config_file),
        )
        config = config_mod.read_config_file(Path(config_file))
        b2_key_id = config.get("b2_key_id") or os.environ.get("B2_KEY_ID")
        b2_key = config.get("b2_key", os.environ.get("B2_KEY"))
        b2_bucket = config.get("b2_bucket") or os.environ.get("B2_BUCKET")

        if config.get("use_b2_simulation", False):
            fake_api = _SimulatedB2API()
            bucket = fake_api.bucket
            b2_bucket = fake_api.bucket_name
        else:
            bucket = None

        assert isinstance(b2_key, str)
        assert isinstance(b2_key_id, str)
        assert isinstance(b2_bucket, str)
        return B2Storage(
            local_path=Path(config["local_path"]),
            remote_path=Path(config["b2_prefix"]),
            b2_bucket=b2_bucket,
            b2_key_id=b2_key_id,
            b2_key=b2_key,
            _bucket=bucket,
        )

    @property
    def storage_path(self) -> Path:
        return self.local_path

    @property
    def bucket(self) -> b2_api.Bucket:
        if self._bucket is None:
            self._bucket = self._connect_b2()
        return self._bucket

    @property
    def b2(self) -> b2_api.B2Api:
        return self.bucket.api

    def _connect_b2(self) -> b2_api.Bucket:
        b2 = b2_api.B2Api()
        b2.authorize_account("production", self.b2_key_id, self.b2_key)
        return b2.get_bucket_by_name(self.b2_bucket)

    # def save(self, obj: Serializable, key: str, upload: bool = False) -> None:
    #    with open(self / key / "state.json", "w") as f:
    #        json.dump(obj.state_dict(), f)

    @contextlib.contextmanager
    def open(self, key: PATH_LIKE, mode: str = "r") -> Iterator[IO]:
        path = self / key
        if not path.exists() and "r" in mode or "a" in mode:
            self.download_file(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        f = open(path, mode)
        yield f
        f.close()

    def ls(self, key: PATH_LIKE) -> Iterator[Path]:
        yield from (self.local_path / key).iterdir()

    def remote_ls(
        self, key: PATH_LIKE = "", recursive: bool = False
    ) -> Iterator[Path]:
        for fid, _ in self.bucket.ls(
            str(self.remote_path / key), recursive=recursive
        ):
            yield Path(fid.file_name[len(str(self.remote_path)) :])

    def remove(
        self, key: PATH_LIKE, local: bool = True, remote: bool = False
    ) -> Iterator[Path]:
        if remote and not local:
            raise ValueError(
                "It is not a good idea to remove remote files "
                "while keeping the local files. "
                f"Key: {key}"
            )
        if remote:
            logger.info(f"Removing remote: {key}")
            for fid, _ in self.bucket.ls(str(self.remote_path / key)):
                fid.delete()
                yield Path(fid.file_name[len(str(self.remote_path)) :])
        if local:
            logger.info(f"Removing local: {key}")
            shutil.rmtree(self / key)

    def get_b2_sync_url(self, key: PATH_LIKE) -> str:
        path = self.remote_path / key
        return f"b2://{self.b2_bucket}/{str(path)}"

    def _b2_encryption(self) -> b2_api.BasicSyncEncryptionSettingsProvider:
        return b2_api.BasicSyncEncryptionSettingsProvider(
            read_bucket_settings={self.b2_bucket: None},
            write_bucket_settings={self.b2_bucket: None},
        )

    def download_file(self, key: PATH_LIKE) -> None:
        remote_name = self.remote_path / key
        local_name = self / key
        logger.info(f"Downloading file: {remote_name} -> {local_name}")
        downloaded = self.bucket.download_file_by_name(str(remote_name))
        downloaded.save_to(str(local_name))

    def sync(self, source: str, destination: str) -> None:
        logger.info(f"Sync: {source} -> {destination}")
        source = b2_api.parse_sync_folder(source, self.b2)
        destination = b2_api.parse_sync_folder(destination, self.b2)
        for folder in [source, destination]:
            if isinstance(folder, b2_api.LocalFolder):
                os.makedirs(folder.root, exist_ok=True)

        policies_manager = b2_api.ScanPoliciesManager(exclude_all_symlinks=True)

        synchronizer = b2_api.Synchronizer(
            max_workers=10,
            policies_manager=policies_manager,
            dry_run=False,
            allow_empty_source=True,
        )

        no_progress = False

        with b2_api.SyncReport(sys.stdout, no_progress) as reporter:
            synchronizer.sync_folders(
                source_folder=source,
                dest_folder=destination,
                now_millis=int(round(time.time() * 1000)),
                reporter=reporter,
                encryption_settings_provider=self._b2_encryption(),
            )

    def get_remote_path(self, key: PATH_LIKE) -> Path:
        return self.remote_path / key

    def download(self, key: PATH_LIKE) -> Path:
        source = self.get_b2_sync_url(key)
        destination = self.local_path / key
        self.sync(source, str(destination))
        return destination

    def upload(self, key: PATH_LIKE) -> str:
        local_path = self / key
        if not local_path.is_dir():
            raise NotADirectoryError(f"Can only upload directories. Got: {key}")
        if not local_path.exists():
            raise FileNotFoundError(f"Directory does not exists. Got: {key}")
        source = str(local_path)
        assert local_path
        destination = self.get_b2_sync_url(key)
        self.sync(source, destination)
        return destination


_global_storage: Optional[Storage] = None


def get_storage(config_file: PATH_LIKE, reload: bool = False) -> Storage:
    global _global_storage
    if _global_storage is None or reload:
        return B2Storage.from_file(config_file)
    return _global_storage
