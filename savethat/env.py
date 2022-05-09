from __future__ import annotations

import getpass
import importlib
import os
import socket
from pathlib import Path
from typing import Any, Optional, Union

import toml
from loguru import logger

# from savethat import utils


_project_dir: Optional[Path] = None
_enviroment_file: Optional[Path] = None


def set_project_dir(path: Path) -> None:
    logger.info(f"Set project dir: {path}.", project_dir=path)
    global _project_dir
    _project_dir = path


def infer_project_dir(package: Optional[str] = None) -> Path:
    global _project_dir
    if _project_dir is not None:
        return _project_dir

    if package is not None:
        module = importlib.import_module(package)
        assert module.__file__ is not None
        file = Path(module.__file__)
        project_dir = file.parent / ".."
    else:
        project_dir = Path(os.curdir)

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
    logger.info(
        f"Guessed project_dir to {project_dir}", project_dir=project_dir
    )
    return project_dir


def find_enviroment_file(project_dir: Optional[Path] = None) -> Path:
    if project_dir is None:
        project_dir = infer_project_dir()

    if _enviroment_file is not None:
        return _enviroment_file

    env_dir = project_dir / "env"
    assert env_dir.exists()
    username = getpass.getuser()
    host = socket.gethostname()
    env_file = env_dir / f"{username}@{host}.toml"
    if not env_file.exists():
        env_file = env_dir / "default.toml"

    set_enviroment_file(env_file)
    return env_file


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
