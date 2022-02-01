"""util functions."""

from __future__ import annotations

import contextlib
import copy
import dataclasses
import hashlib
import importlib
import pdb
import pkgutil
import sys
import time
import traceback
import types
from datetime import datetime
from types import ModuleType, TracebackType
from typing import Any, Callable, Iterator, Optional, Sequence, TypeVar, Union

import numpy as np

T = TypeVar("T")


def ifnone(maybe_none: Optional[T], default: Union[types.LambdaType, T]) -> T:
    if maybe_none is not None:
        return maybe_none
    elif isinstance(default, types.LambdaType):
        return default()
    else:
        return default


def combine_hash(hashes: list[str]) -> str:
    m = hashlib.sha256()
    for h in hashes:
        m.update(h.encode("utf-8"))
    return m.hexdigest()


def strict_union(*dicts: dict) -> dict:
    merged = {}
    for dictionary in dicts:
        for k, v in dictionary.items():
            if k in merged:
                raise ValueError(f"key {k} already exists.")
            merged[k] = copy.deepcopy(v)
    return merged


def flatten(x: Union[T, Sequence[T], Sequence[Any]]) -> list[T]:
    def flatten(x: Union[T, Sequence[T], Sequence[Any]]) -> Iterator[T]:
        if isinstance(x, (list, tuple)):
            for gen in [flatten(xi) for xi in x]:
                yield from gen
        else:
            yield x  # type: ignore

    return list(flatten(x))


def concat_dicts(
    dicts: list[dict[str, np.ndarray]],
    axis: int = 0,
) -> dict[str, np.ndarray]:
    keys = dicts[0].keys()
    return {
        key: np.concatenate([d[key] for d in dicts], axis=0) for key in keys
    }


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
    for loader, name, is_pkg in pkgutil.walk_packages(
        package.__path__  # type:ignore
    ):
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


def prefix_dict(prefix: str, dictionary: dict[str, Any]) -> dict[str, Any]:
    return {f"{prefix}.{key}": value for key, value in dictionary.items()}


def timestamp(clear_microseconds: bool = True) -> str:
    date = datetime.utcnow()
    if clear_microseconds:
        date = date.replace(microsecond=0)
    return date.isoformat()


# ------------------------------------------------------------------------------


class timeit:
    def __enter__(self) -> timeit:
        self.t = time.perf_counter()
        return self

    def __exit__(
        self,
        t: Optional[type[BaseException]] = None,
        value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None,
    ) -> Optional[bool]:
        self.e = time.perf_counter()
        return None

    def __float__(self) -> float:
        return float(self.e - self.t)

    def __coerce__(self, other: Any) -> tuple[float, Any]:
        return (float(self), other)

    def __str__(self) -> str:
        return str(float(self))

    def __repr__(self) -> str:
        return str(float(self))
