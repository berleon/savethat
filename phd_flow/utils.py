"""util functions."""

from __future__ import annotations

import contextlib
import dataclasses
import importlib
import pdb
import pkgutil
import sys
import time
import traceback
from datetime import datetime, timezone
from types import ModuleType
from typing import Any, Callable, Iterator, Optional, TypeVar

T = TypeVar("T")


@contextlib.contextmanager
def pdb_post_mortem(enable: bool = True) -> Iterator[None]:
    if enable:
        try:
            yield
        except Exception:
            extype, value, tb = sys.exc_info()
            traceback.print_exc()
            pdb.post_mortem(tb)
    else:
        yield


def default(factory: Callable[[], T]) -> T:
    return dataclasses.field(default_factory=factory)


def load_class(module_name: str, class_name: Optional[str] = None) -> type[Any]:
    if class_name is None:
        parts = module_name.split(".")
        module_name = ".".join(parts[:-1])
        class_name = parts[-1]
    module = importlib.import_module(module_name)
    clazz = getattr(module, class_name)
    return clazz


def import_submodules(
    package_name: str,
    recursive: bool = True,
    ignore_errors: bool = True,
) -> dict[str, ModuleType]:
    """Import all submodules of a module, recursively, including subpackages."""
    package = importlib.import_module(package_name)
    results = {}
    for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
        if name == "__main__":
            continue
        try:
            full_name = package.__name__ + "." + name
            results[full_name] = importlib.import_module(full_name)
            if recursive and is_pkg:
                results.update(import_submodules(full_name))
        except ModuleNotFoundError:
            if not ignore_errors:
                raise
    return results


def get_module_and_class(obj: Any) -> tuple[str, str]:
    return type(obj).__module__, type(obj).__qualname__


def isoformat_now(clear_microseconds: bool = True) -> str:
    date = datetime.utcnow()
    if clear_microseconds:
        date = date.replace(microsecond=0)
    return date.isoformat()


def parse_time(date_str: str) -> datetime:
    if date_str.endswith("Z"):
        date_str = date_str[:-1]

    if "T" not in date_str:
        date_str += "T00:00:00"
    if "+" not in date_str:
        date_str += "+00:00"

    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        parsed_time = time.strptime(date_str, "%Y-%m-%dT%H-%M-%S%z")
        return datetime(*(parsed_time[0:6]), tzinfo=timezone.utc)
