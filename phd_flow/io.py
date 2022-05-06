from __future__ import annotations

import abc
import contextlib
import dataclasses
import json
import os
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import IO, Any, Iterable, Iterator, Optional, TypeVar, Union, cast

import b2sdk.v2 as b2_api
import pandas as pd
from loguru import logger

from phd_flow import env as env_mod
from phd_flow import utils

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
    ) -> None:
        """Removes the `key` locally or remotely.

        Use with care, this will also delete any subdirectories.
        It is not allowed to remove a `key` only on the remote.

        Args:
            key: key to remove
            local: remove the key locally
            remote: remove the key on the cloud storage
        """

    @abc.abstractmethod
    def ls(self, key: PATH_LIKE) -> Iterator[Path]:
        pass

    @staticmethod
    def _runs_from_paths(paths: Iterable[Path]) -> dict[Path, set[Path]]:
        runs = defaultdict(set)
        for path in paths:
            if ".bzEmpty" in str(path):
                continue
            first_part = Path(path.parts[0])
            runs[first_part].add(path)
        return runs

    @staticmethod
    def get_date_of_run(run: PATH_LIKE) -> datetime:
        """Returns the date of the run."""
        date_str = str(run).split("_")[-1]
        return utils.parse_time(date_str)

    def find_runs_as_df(
        self,
        path: PATH_LIKE,
        remote: bool = True,
        only_failed: bool = False,
        only_completed: bool = False,
        absolute: bool = False,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None,
    ) -> Union[Iterator[tuple[Path, list[Path]]], pd.DataFrame]:
        """Finds all runs in `path` and returns them as a DataFrame.

        Args:
            path: the path to search for runs.
            remote: if true, search the remote storage.
            only_failed: if true, only return runs that failed.
            only_completed: if true, only return runs that completed.
            absolute: if true, return the absolute path of the run.
            before: only return runs before this date.
            after: only return runs after this date.

        Returns:
            A DataFrame with the runs information.
        """

        data = []
        for run, run_files in self.find_runs(
            path,
            remote=remote,
            only_failed=only_failed,
            only_completed=only_completed,
            absolute=absolute,
            before=before,
            after=after,
        ):
            with open(self / run / "args.json") as f:
                args = json.load(f)

            run_info = {
                "key": str(run),
                "date": self.get_date_of_run(run),
                "completed": run / "results.pickle" in run_files,
                "files": [str(f) for f in run_files],
            }
            run_info.update(args)
            data.append(run_info)
        return pd.DataFrame(data)

    def find_runs(
        self,
        path: PATH_LIKE,
        remote: bool = True,
        only_failed: bool = False,
        only_completed: bool = False,
        absolute: bool = False,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None,
    ) -> Iterator[tuple[Path, list[Path]]]:
        """Finds all runs in `path`.

        Args:
            path: the path to search for runs.
            remote: if true, search the remote storage.
            only_failed: if true, only return runs that failed.
            only_completed: if true, only return runs that completed.
            absolute: if true, return the absolute path of the run.
            before: only return runs before this date.
            after: only return runs after this date.

        Returns:
            A generator of tuples of the form (run, files) where `run` is the
            run path and `files` is a list of files in that run.
        """

        # It looks inefficient too loop over all files, but b2 actually
        # does loop over all files anyway.

        def format_path(path: PATH_LIKE) -> Path:
            if absolute:
                return self / path
            else:
                return Path(path)

        if remote:
            path_gen = iter(self.remote_ls(path, recursive=True))
        else:
            path_gen = iter(self.ls(path))

        for run, run_paths in self._runs_from_paths(path_gen).items():
            if run / "args.json" not in run_paths:
                # does not look like a run
                continue

            result_file = run / "results.pickle"

            if only_failed and result_file in run_paths:
                continue

            if only_completed and result_file not in run_paths:
                continue

            if before is not None or after is not None:
                date = self.get_date_of_run(str(run))
                if before is not None and date > before:
                    continue
                if after is not None and date < after:
                    continue

            yield format_path(run), list(map(format_path, sorted(run_paths)))


class SimulatedB2API:
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


STORAGE = TypeVar("STORAGE", bound="B2Storage")


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

    @classmethod
    def from_file(cls: type[STORAGE], env_file: PATH_LIKE) -> STORAGE:
        env = env_mod.read_env_file(Path(env_file))
        return cls.from_env(env)

    @classmethod
    def from_env(cls: type[STORAGE], env: dict[str, Any]) -> STORAGE:
        if env.get("use_b2_simulation", False):
            fake_api = SimulatedB2API()
            bucket = fake_api.bucket
            b2_bucket = fake_api.bucket_name
            b2_key_id = fake_api.application_key_id
            b2_key = fake_api.master_key
        else:
            b2_key_id = env.get("b2_key_id") or os.environ.get("B2_KEY_ID")
            b2_key = env.get("b2_key", os.environ.get("B2_KEY"))
            b2_bucket = cast(
                str, env.get("b2_bucket") or os.environ.get("B2_BUCKET")
            )
            bucket = None

        assert isinstance(b2_key, str)
        assert isinstance(b2_key_id, str)
        assert isinstance(b2_bucket, str)
        return cls(
            local_path=Path(env["local_path"]),
            remote_path=Path(env["b2_prefix"]),
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
            str(self.remote_path), recursive=recursive
        ):
            prefix = str(self.remote_path / key)
            if fid.file_name.startswith(prefix):
                yield Path(
                    fid.file_name[len(str(self.remote_path)) :].lstrip("/")
                )

    def remove(
        self, key: PATH_LIKE, local: bool = True, remote: bool = False
    ) -> None:
        if remote and not local:
            raise ValueError(
                "It is not a good idea to remove remote files "
                "while keeping the local files. "
                f"Key: {key}"
            )

        if remote:
            logger.info(f"Deleting remote: {key}")
            for fid, _ in self.bucket.ls(str(self.remote_path / key)):
                fid.delete()
        if local and (self / key).exists():
            logger.info(f"Deleting local: {key}")
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


def get_storage(env_file: PATH_LIKE, reload: bool = False) -> Storage:
    global _global_storage
    if _global_storage is None or reload:
        return B2Storage.from_file(env_file)
    return _global_storage
