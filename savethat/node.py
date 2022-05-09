from __future__ import annotations

import abc
import copy
import dataclasses
import json
import pickle
import random
import sys
from pathlib import Path
from typing import Any, Callable, Generic, Optional, TypeVar, Union

import reproducible as reproducible_mod

from savethat import env, io, utils
from savethat.args import Args
from savethat.log import logger

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
        path=str(env.infer_project_dir()), allow_dirty=True, diff=True
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
        env: dict[str, Any],
        reproducible: Optional[reproducible_mod.Context] = None,
    ):
        self.key: str = str(key)
        self.storage = storage
        self.args = args
        self.env = env
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
        self.logger = logger.bind(key=self.key)
        self.setup()

    @property
    def key_as_path(self) -> Path:
        return Path(self.key)

    def setup(self):
        pass

    def init_reproducible(self) -> reproducible_mod.Context:
        return get_reproducible()

    def register_pre_run_hook(
        self,
        hook: Callable[[Node[ARGS, T]], None],
    ) -> HookHandle:
        """Registers a hook which is executed before the node is run."""
        idx = random.randint(0, 2**64)
        self._hooks_pre_run[idx] = hook
        return HookHandle(self._hooks_pre_run, idx)

    def register_run_hook(
        self, hook: Callable[[Node[ARGS, T], T], None]
    ) -> HookHandle:
        """Registers a hook which is executed after the node is run."""
        idx = random.randint(0, 2**64)
        self._hooks_run[idx] = hook
        return HookHandle(self._hooks_run, idx)

    @classmethod
    def create_new_key(cls) -> str:
        """Returns a new key for this class.

        As default, it will return the classname + the current time (isoformat).
        """
        return cls.__qualname__ + "_" + utils.isoformat_now().replace(":", "-")

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
            self.logger.info(
                "Run Node",
                node=self.name,
                key=str(self.key),
                output_dir=str(self.output_dir),
            )
            args_file = str(self.output_dir / "args.json")
            self.args.save(args_file)
            self.logger.info(f"Saving arguments to: {args_file}")
            with open(self.output_dir / "node.json", "w") as f:
                json.dump(self._node_info(), f, indent=2)
            self.reproducible.export_json(self.output_dir / "reproducible.json")

            self.storage.upload(self.key)
            result = self._run()

            pickle_file = self.output_dir / "results.pickle"
            self.logger.info(f"Saving results to to: {pickle_file}")
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
    args: Union[None, list[str], tuple[str], dict[str, Any], ARGS] = None,
    env_file: Optional[io.PATH_LIKE] = None,
    key_prefix: Optional[str] = None,
) -> Node[ARGS, T]:
    """Creates a new node.

    Args:
        node_cls: the class of the node
        env_file: path to the env file
        argv: comandline arguments used to creating the node's args.
        args_dict: if given, the arguments will be loaded from this dict.
    """

    args_cls: type[ARGS] = node_cls.get_args_class()

    if isinstance(args, args_cls):
        parsed_args = args
    elif isinstance(args, dict):
        parsed_args = args_cls.from_dict(args)
    elif isinstance(args, (list, tuple)):
        parsed_args = args_cls.parse_args(args=args)
    else:  # args is None:
        parsed_args = args_cls.parse_args(args=sys.argv)

    if env_file is None:
        env_file = env.find_enviroment_file()

    env_dict = env.read_env_file(env_file)
    storage = io.B2Storage.from_env(env_dict)
    key = node_cls.create_new_key()
    if key_prefix:
        key = key_prefix + key
    node = node_cls(key, storage, parsed_args, env_dict)
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
            node1 = first(
                self.key_as_path / node_name(first),
                self.storage,
                self.args,
                self.env,
            )

            res1 = node1.run()
            args2 = operator(node1, res1)
            node2 = second(
                self.key_as_path / node_name(second),
                self.storage,
                args2,
                self.env,
            )
            return node2.run()

    return JoinNode
