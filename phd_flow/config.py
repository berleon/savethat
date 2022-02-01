from __future__ import annotations

import getpass
import importlib
import socket
from pathlib import Path
from typing import Any, Optional

import toml
from loguru import logger

# from phd_flow import utils


_project_dir: Optional[Path] = None


def set_project_dir(path: Path):
    logger.info(f"Set project dir: {path}.", project_dir=path)
    global _project_dir
    _project_dir = path


def guess_project_dir(package: Optional[str] = None) -> Path:
    global _project_dir
    if _project_dir is not None:
        return _project_dir

    if package is not None:
        module = importlib.import_module(package)
        assert module.__file__ is not None
        file = Path(module.__file__)
    else:
        file = Path(__file__)
    project_dir = file.parent / ".."
    project_dir = project_dir.resolve()
    _project_dir = project_dir
    logger.info(
        f"Guessed project_dir to {project_dir}", project_dir=project_dir
    )
    return project_dir


def find_config_file(project_dir: Path) -> Path:
    config_dir = project_dir / "config"
    assert config_dir.exists()
    username = getpass.getuser()
    host = socket.gethostname()
    config_file = config_dir / f"{username}@{host}.toml"
    if not config_file.exists():
        config_file = config_dir / "default.toml"

    return config_file


def read_config_file(path: Path) -> dict[str, Any]:
    def _replace_placeholder(value: Any) -> Any:
        if isinstance(value, str):
            return value.replace("${PROJECT_ROOT}", str(_project_dir))
        else:
            return value

    with open(path) as f:
        config = dict(toml.load(f))
    return {k: _replace_placeholder(v) for k, v in config.items()}
