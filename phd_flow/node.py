from __future__ import annotations

import abc
import copy
import dataclasses
import pickle
import random
import sys
from pathlib import Path
from typing import Any, Callable, Generic, Optional, TypeVar, Union

import reproducible as reproducible_mod
from phd_flow.args import Args
from phd_flow.log import logger

from phd_flow import config, io, utils

T = TypeVar("T")
ARGS = TypeVar("ARGS", bound="Args")


@dataclasses.dataclass
class HookHandle:
    hooks: dict
    idx: int

    def remove(self):
        del self.hooks[self.idx]


_reproducible: Optional[reproducible_mod.Context] = None


def get_reproducible(reload: bool = False) -> reproducible_mod.Context:
    global _reproducible
    if _reproducible is not None and not reload:
        return copy.deepcopy(_reproducible)

    reproducible = reproducible_mod.Context()
    reproducible.add_repo(
        path=str(config.guess_project_dir()), allow_dirty=True, diff=True
    )
    reproducible.add_editable_repos()
    reproducible.add_pip_packages()
    reproducible.add_cpu_info()
    _reproducible = reproducible
    return copy.deepcopy(reproducible)


class Node(Generic[ARGS, T], metaclass=abc.ABCMeta):
    """A Node is a self-contained unit of computation.

    Attributes:
        key: A unique key that references this node
        storage: The B2 storage object
        args: The parsed arguments.
    """

    @classmethod
    def get_args_class(cls) -> type[ARGS]:
        """Returns the type of the ARGS generic.

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
                "  - or overwrite `get_args_class` in your node class "
                f"{cls.__qualname__}.\n"
            )
        return args_cls

    def __init__(
        self,
        key: io.PATH_LIKE,
        storage: io.Storage,
        args: ARGS,
        reproducible: Optional[reproducible_mod.Context] = None,
    ):
        self.key = Path(key)
        self.storage = storage
        self.args = args
        if reproducible is None:
            self.reproducible = self.init_reproducible()

        self.reproducible.add_data(
            "node.__module__", str(type(self).__module__)
        )
        self.reproducible.add_data(
            "node.__qualname__", str(type(self).__qualname__)
        )
        self._hooks_pre_run: dict[int, Callable[[Node[ARGS, T]], None]] = {}
        self._hooks_run: dict[int, Callable[[Node[ARGS, T], T], None]] = {}

    def init_reproducible(self) -> reproducible_mod.Context:
        return get_reproducible()

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
        return cls.__qualname__ + "_" + utils.isoformat_now()

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

            result = self._run()

            self.reproducible.export_json(self.output_dir / "node.json")

            pickle_file = self.output_dir / "results.pickle"
            logger.info(f"Saving results to to: {pickle_file}")
            with open(pickle_file, "wb") as fb:
                pickle.dump(result, fb)

            for hook in self._hooks_run.values():
                hook(self, result)
            return result
        finally:
            try:
                self.reproducible.export_json(self.output_dir / "node.json")
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
    args_dict: Optional[dict[str, Any]] = None,
) -> Node[ARGS, T]:
    """Creates a new node.

    Args:
        node_cls: the class of the node
        config_file: path to the config file
        argv: comandline arguments used to creating the node's args.
        args_dict: if given, the arguments will be loaded from this dict.
    """
    if argv is None:
        argv = sys.argv

    args_cls: type[ARGS] = node_cls.get_args_class()

    if args_dict:
        args = args_cls.from_dict(args_dict)
    else:
        args = args_cls.parse_args(args=argv)
    storage = io.get_storage(config_file)
    key = node_cls.create_new_key()
    node = node_cls(key, storage, args)
    return node


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
        @classmethod
        def get_args_class(cls) -> type[ARGS1]:
            return first.get_args_class()

        def _run(self):
            node1 = first(self.key / node_name(first), self.storage, self.args)

            res1 = node1.run()
            args2 = operator(node1, res1)
            node2 = second(self.key / node_name(second), self.storage, args2)
            return node2.run()

    return JoinNode
