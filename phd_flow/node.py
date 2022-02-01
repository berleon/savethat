from __future__ import annotations

import abc
import dataclasses
import json
import pickle
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, ClassVar, Generic, Optional, TypeVar, Union

import tap
from loguru import logger

from phd_flow import config, io, log, utils


class Args(tap.Tap):
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


T = TypeVar("T")
ARGS = TypeVar("ARGS", bound="Args")


@dataclasses.dataclass
class HookHandle:
    hooks: dict
    idx: int

    def remove(self):
        del self.hooks[self.idx]


class Node(Generic[ARGS, T], io.Serializable, metaclass=abc.ABCMeta):
    """A Node is a self-contained unit of computation.

    Args:
        - key: A unique key that references this node
        - storage: The B2 storage object
        - args: The parsed arguments.
    """

    @classmethod
    @property
    def args_class(cls) -> type[ARGS]:
        """Returns a class instance of ARGS.

        The default behavior is to infer the class from appending "Args" to the
        node's classname, e.g. for `FitOLS` it would return `FitOLSArgs`.

        If you want to use another classname, you have to overwrite this method.
        """
        expected_name = cls.__qualname__ + "Args"
        try:
            args_cls = utils.load_class(cls.__module__, expected_name)
        except ImportError or ValueError:
            raise AttributeError(
                f"Did not found argument class with name {expected_name}.\n"
                "You have two options:"
                "  - either create a class {expected_name} that inhirents"
                " from node.Args\n"
                "  - or overwrite `args_class` in your node class "
                f"{cls.__qualname__}.\n"
            )
        return args_cls

    def __init__(self, key: io.PATH_LIKE, storage: io.Storage, args: ARGS):
        self.key = Path(key)
        self.storage = storage
        self.args = args
        self._hooks_pre_run: dict[int, Callable[[Node[ARGS, T]], None]] = {}
        self._hooks_run: dict[int, Callable[[Node[ARGS, T], T], None]] = {}

    def register_pre_run_hook(
        self,
        hook: Callable[[Node[ARGS, T]], None],
    ) -> HookHandle:
        """Registers a hook which is executed before the node is run."""
        idx = random.randint(0, 2 ** 64)
        self._hooks_pre_run[idx] = hook
        return HookHandle(self._hooks_pre_run, idx)

    def register_run_hook(
        self, hook: Callable[[Node[ARGS, T], T], None]
    ) -> HookHandle:
        """Registers a hook which is executed after the node is run."""
        idx = random.randint(0, 2 ** 64)
        self._hooks_run[idx] = hook
        return HookHandle(self._hooks_run, idx)

    @classmethod
    def create_new_key(cls) -> str:
        """Returns a new key for this class.

        As default, it will return the classname + the current time (isoformat).
        """
        return cls.__qualname__ + "_" + datetime.utcnow().isoformat()

    def _node_info(self) -> dict[str, str]:
        return {
            "class": type(self).__qualname__,
            "module": type(self).__module__,
        }

    def run(self) -> T:
        """Executes the Node.

        If the output directory (self.storage / key), an error is raised.
        To execute nodes a second time, create a new one with a new key.
        """

        self.output_dir.mkdir(parents=True, exist_ok=False)
        try:
            for pre_hook in self._hooks_pre_run.values():
                pre_hook(self)
            logger.info(
                "Run Node",
                node=self.name,
                key=str(self.key),
                output_dir=str(self.output_dir),
            )
            args_file = str(self.output_dir / "args.json")
            self.args.save(args_file)
            logger.info(f"Saving arguments to: {args_file}")

            with (self.output_dir / "node.json").open("w") as f:
                json.dump(self._node_info(), f)

            result = self._run()
            pickle_file = self.output_dir / "results.pickle"
            logger.info(f"Saving results to to: {pickle_file}")
            with open(pickle_file, "wb") as fb:
                pickle.dump(result, fb)

            for hook in self._hooks_run.values():
                hook(self, result)
            return result
        finally:
            self.storage.upload(self.key)

    @abc.abstractmethod
    def _run(self) -> T:
        """A subclasses should implement the _run method."""
        pass

    @property
    def output_dir(self) -> Path:
        """The output directory of the node (storage / key)."""
        return self.storage / self.key

    @property
    def name(self) -> str:
        """The name of the Node."""
        return type(self).__qualname__


def create_node(
    node_cls: type[Node[ARGS, T]],
    config_file: io.PATH_LIKE,
    argv: Optional[list[str]] = None,
) -> Node[ARGS, T]:
    if argv is None:
        argv = sys.argv

    args: ARGS = node_cls.args_class().parse_args(args=argv)  # type: ignore
    storage = io.get_storage(config_file)
    key = node_cls.create_new_key()
    node = node_cls(key, storage, args)
    return node


def run_main(
    package: str,
    config_file: Optional[io.PATH_LIKE] = None,
    argv: Optional[list[str]] = None,
) -> Optional[tuple[Node[ARGS, T], T]]:
    def print_help() -> None:
        print("Here is a list with all available actions:", file=sys.stderr)
        print("   run      Runs a node", file=sys.stderr)
        print("   list     List all avialbe nodes", file=sys.stderr)

    def print_no_action() -> None:
        print("Error, no action was given!", file=sys.stderr)
        print(
            f"Use `{arg_list[0]} help` to print a list of available actions.",
            file=sys.stderr,
        )

    print("Called run_main")
    utils.import_submodules(package)
    nodes = {cls.__qualname__: cls for cls in Node.__subclasses__()}

    if argv is None:
        arg_list = sys.argv
    else:
        arg_list = argv

    if config_file is None:
        config_file = config.find_config_file(config.guess_project_dir(package))

    if len(arg_list) == 1:
        print_no_action()
        return None

    action = arg_list[1]
    if action in ["help", "--help", "-h"]:
        print_help()
    elif action == "run":
        node_name = arg_list[2]
        node_cls: type[Node[ARGS, T]] = nodes[node_name]  # type: ignore

        created_node: Node[ARGS, T] = create_node(
            node_cls, config_file, arg_list[3:]
        )
        created_node.register_pre_run_hook(
            lambda n: log.setup_logger(n.output_dir)
        )
        result = created_node.run()
        logger.info(
            "Finished running Node",
            key=str(created_node.key),
            output_dir=str(created_node.output_dir),
        )
        return created_node, result
    elif action == "list":
        for name, node in nodes.items():
            print(f"{name}:             {node.__module__}")
            print(node.__doc__)
    return None


def node_name(node: Union[Node, type[Node]]) -> str:
    if isinstance(node, Node):
        node_type = type(node)
    else:
        node_type = node

    return node_type.__qualname__


T1 = TypeVar("T1")
T2 = TypeVar("T2")
ARGS1 = TypeVar("ARGS1", bound="Args")
ARGS2 = TypeVar("ARGS2", bound="Args")


def join(
    first: type[Node[ARGS1, T1]],
    second: type[Node[ARGS2, T2]],
    operator: Callable[[Node[ARGS1, T1], T1], ARGS2],
) -> type[Node[ARGS1, T2]]:
    class JoinNode(Node[ARGS1, T2]):
        def _run(self):
            node1 = first(self.key / node_name(first), self.storage, self.args)

            res1 = node1.run()
            args2 = operator(node1, res1)
            node2 = second(self.key / node_name(second), self.storage, args2)
            return node2.run()

    return JoinNode
