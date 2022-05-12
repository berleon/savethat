from __future__ import annotations

import getpass
import importlib
import socket
from pathlib import Path
from typing import Any, Optional, Union

import anyconfig
import toml
from loguru import logger

# from savethat import utils


_project_dir: Optional[Path] = None
_enviroment_file: Optional[Path] = None


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


def set_enviroment_file(path: Union[Path, str]) -> None:
    global _enviroment_file
    _enviroment_file = Path(path)


def read_env_file(path: Union[Path, str]) -> dict[str, Any]:
    def _replace_placeholder(value: Any) -> Any:
        if isinstance(value, str):
            if "${PROJECT_ROOT}" in value:
                if _project_dir is None:
                    raise ValueError(
                        "project_dir is not set. Use set_project_dir()"
                    )
                return value.replace("${PROJECT_ROOT}", str(_project_dir))
            else:
                return value
        else:
            return value

    logger.info(
        f"Loading env from file: {str(path)}",
        file=str(path),
        project_dir=str(_project_dir),
    )
    with open(path) as f:
        env = dict(toml.load(f))
    return {k: _replace_placeholder(v) for k, v in env.items()}
