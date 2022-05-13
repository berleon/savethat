from __future__ import annotations

import dataclasses
import getpass
import importlib
import os
import socket
from pathlib import Path
from typing import Any, Optional, Union

import anyconfig
import toml
from loguru import logger

# from savethat import utils


_project_dir: Optional[Path] = None


def set_project_dir(path: Path) -> None:
    logger.info(f"Set project dir: {path}.", project_dir=path)
    global _project_dir
    _project_dir = path


def get_project_dir() -> Path:
    assert _project_dir is not None
    return _project_dir


def infer_project_dir(package: str) -> Path:
    global _project_dir
    if _project_dir is not None:
        return _project_dir

    if package is not None:
        module = importlib.import_module(package)
        assert module.__file__ is not None
        file = Path(module.__file__)
        module_dir = file.parent
        if module_dir.parts[-1] == "src":
            project_dir = module_dir.parent.parent
        else:
            project_dir = module_dir.parent

    project_dir = project_dir.resolve()
    if not (
        (project_dir / "pyproject.toml").exists()
        or (project_dir / "setup.py").exists()
    ):
        raise Exception(
            f"Inferred project_dir '{project_dir}' does not "
            "look like a python package."
        )
    _project_dir = project_dir
    logger.info(f"Using {project_dir} as project dir", project_dir=project_dir)
    return project_dir


def load_host_settings(directory: Path, ext: str = "toml") -> dict[str, Any]:
    username = getpass.getuser()
    host = socket.gethostname()
    file = directory / f"{username}@{host}.{ext}"
    if not file.exists():
        file = directory / f"default.{ext}"

    if not file.exists():
        raise FileNotFoundError(f"No env file found in {directory}")

    return anyconfig.load(file)


def _get_credential_file(file_name: Union[Path, str, None] = None) -> Path:
    if file_name is None:
        return Path(
            os.environ.get(
                "SAVETHAT_CREDENTIALS", "~/savethat_credentials.toml"
            )
        ).expanduser()
    else:
        return Path(file_name)


@dataclasses.dataclass
class B2Credentials:
    b2_key_id: str
    b2_key: str
    b2_bucket: str
    remote_path: str
    local_path: str
    skip_syncing: bool = False

    @staticmethod
    def no_syncing(local_path: Union[str, Path]) -> B2Credentials:
        return B2Credentials(
            "", "", "", "", local_path=str(local_path), skip_syncing=True
        )


def load_credentials(
    package_name: str, file_name: Union[Path, str, None] = None
) -> B2Credentials:
    credential_file = _get_credential_file(file_name)
    logger.debug(f"Reading credentials from {credential_file}")
    with open(credential_file) as f:
        return B2Credentials(**anyconfig.load(f)[package_name])


def store_credentials(
    package_name: str,
    credentials: B2Credentials,
    file_name: Union[None, str, Path] = None,
) -> None:
    credential_file = _get_credential_file(file_name)
    logger.debug(f"Saving credentials to {credential_file}")

    if credential_file.exists():
        with open(credential_file) as f:
            config = toml.load(f)
    else:
        config = {}

    config[package_name] = dataclasses.asdict(credentials)

    with open(credential_file, "w") as f:
        toml.dump(config, f)


def setup_credentials(
    project_dir: Path,
    package: str,
    credential_file: Union[str, Path, None] = None,
) -> B2Credentials:
    """Setup the credentials for the B2 service."""

    def get_local_storage() -> str:
        default_local_storage = str(project_dir.parent / "data_storage")
        local_storage = input(
            f"Path of the local datastorage: [{default_local_storage}]"
        )
        if local_storage == "":
            local_storage = default_local_storage
        return local_storage

    print("Setting up B2 credentials")
    print()
    if input("Do you want to set up remote syncing? [y/n]").lower() != "y":
        print("Skipping remote syncing.")
        print("Warning: Your runs will not be synced to the cloud.")
        credentials = B2Credentials.no_syncing(get_local_storage())

    else:
        b2_key_id = input("Enter your B2 account KEY ID: ")
        b2_key = input("Enter your B2 account KEY: ")
        b2_bucket = input("Enter your B2 bucket name: ")
        b2_prefix = input(
            f"Enter your B2 bucket prefix: [default: '{package}']"
        )
        if b2_prefix == "":
            b2_prefix = package
        credentials = B2Credentials(
            b2_key_id,
            b2_key,
            b2_bucket,
            b2_prefix,
            local_path=get_local_storage(),
        )

    store_credentials(package, credentials, credential_file)
    return credentials
