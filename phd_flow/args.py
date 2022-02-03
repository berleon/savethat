"""util functions."""
from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path
from typing import Any, ClassVar, Optional, Sequence, TypeVar, Union

import tap

T = TypeVar("T")


class TapPatch(tap.Tap):
    def _filter_variables(self, dct: dict[str, Any]) -> dict[str, Any]:
        to_remove = [
            key
            for key, cls in dct.items()
            if hasattr(cls, "__origin__") and cls.__origin__ is ClassVar
        ]

        for varname in list(dct.keys()):
            if varname in to_remove:
                del dct[varname]
        return dct

    def _get_annotations(self) -> dict[str, Any]:
        return self._filter_variables(super()._get_annotations())

    def _get_class_variables(self) -> dict[str, Any]:  # type: ignore
        return self._filter_variables(super()._get_class_variables())


def arg_parser_from_dataclass(cls: type) -> type[TapPatch]:
    """Creates an ArgumentParser from a dataclass using the tap library."""
    dct = dict(cls.__dict__)

    dct["__init__"] = TapPatch.__init__
    dct["from_dict"] = TapPatch.from_dict
    dct["as_dict"] = TapPatch.as_dict
    dct["parse_args"] = TapPatch.parse_args
    dct["process_args"] = TapPatch.process_args
    dct["__setattr__"] = TapPatch.__setattr__

    # This is madness:
    return type(
        cls.__name__ + "PatchedParser",
        cls.__bases__ + (TapPatch,),
        dct,
    )


ARGS = TypeVar("ARGS", bound="Args")


@dataclasses.dataclass(frozen=True)
class Args:
    @classmethod
    def _get_arg_parser(cls: type[ARGS]) -> TapPatch:
        return arg_parser_from_dataclass(cls)()

    @classmethod
    def _get_keys(cls: type[ARGS]) -> list[str]:
        args_parser = cls._get_arg_parser()
        return list(args_parser._get_annotations().keys())

    @classmethod
    def parse_args(
        cls: type[ARGS],
        args: Optional[Sequence[str]] = None,
        known_only: bool = False,
    ) -> ARGS:
        args_parser = cls._get_arg_parser()
        parsed_args = args_parser.parse_args(args, known_only)
        kwargs = {}
        for argname in args_parser._get_annotations().keys():
            kwargs[argname] = getattr(parsed_args, argname)

        try:
            obj = cls(**kwargs)  # type: ignore
        except TypeError as e:
            e.args = e.args + (
                "Maybe you forgot to add @dataclasses.dataclass"
                " to your Args class?",
            )
            raise
        obj.process_args()
        return obj

    @classmethod
    def from_dict(
        cls: type[ARGS],
        state: dict[str, Any],
        skip_unsettable: bool = False,
    ) -> ARGS:
        args_parser = cls._get_arg_parser()
        state = copy.copy(state)

        if "__module__" in state:
            del state["__module__"]
        if "__qualname__" in state:
            del state["__qualname__"]

        args_parser.from_dict(state, skip_unsettable)
        kwargs = {}
        for argname in args_parser._annotations.keys():
            if argname in ["_args_parser"]:
                continue
            kwargs[argname] = getattr(args_parser, argname)
        return cls(**kwargs)  # type: ignore

    def process_args(self) -> None:
        pass

    def as_dict(self, with_class_info: bool = False) -> dict[str, Any]:
        state = {
            argname: getattr(self, argname) for argname in self._get_keys()
        }
        if with_class_info:
            state.update(
                {
                    "__module__": type(self).__module__,
                    "__qualname__": type(self).__qualname__,
                }
            )
        return state

    def save(self, path: Union[Path, str]) -> None:
        state = self.as_dict(with_class_info=True)
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
