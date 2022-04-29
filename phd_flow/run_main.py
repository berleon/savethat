from __future__ import annotations

import argparse
import inspect
import sys
from typing import Optional, TypeVar

import anyconfig
from loguru import logger

from phd_flow import args, env, io, log
from phd_flow import node as node_mod
from phd_flow import utils
from phd_flow.node import Node

ARGS = TypeVar("ARGS", bound="args.Args")
T = TypeVar("T")


class MainRunner:
    def __init__(
        self,
        package: str,
        env_file: Optional[io.PATH_LIKE] = None,
        argv: Optional[list[str]] = None,
    ):
        if argv is None:
            self.argv = sys.argv[1:]
        else:
            self.argv = argv
        use_debug = "--debug" in self.argv
        self.env_file = env_file
        self.package = package
        env.infer_project_dir(self.package)

        utils.import_submodules(package, ignore_errors=False)
        self.nodes = self.find_all_subclasses(debug=use_debug)
        self.create_parser()

    @staticmethod
    def find_all_subclasses(debug: bool = False) -> list[type[Node]]:
        def all_subclasses(cls: type) -> set[type[Node]]:
            if debug:
                logger.info(f"Scanning: {cls.__module__}.{cls.__qualname__}")
            return set(cls.__subclasses__()).union(
                [s for c in cls.__subclasses__() for s in all_subclasses(c)]
            )

        subclasses: set[type[Node]] = all_subclasses(Node)

        qualified_subclasses = []
        for cls in subclasses:
            if inspect.isabstract(cls):
                logger.info(
                    f"`{cls.__module__}.{cls.__qualname__}`"
                    " is an abstract class -- will ignore it."
                )
            else:
                qualified_subclasses.append(cls)

        return sorted(
            qualified_subclasses,
            key=lambda c: (c.__module__, c.__qualname__),
        )

    def create_parser(
        self,
    ):
        self.parser = argparse.ArgumentParser()
        self.parser.set_defaults(func=self.help)
        subparsers = self.parser.add_subparsers()

        list = subparsers.add_parser("list")
        list.set_defaults(func=self.list)

        # create the parser for the "bar" command
        self.run_parser = subparsers.add_parser("run", add_help=False)
        self.run_parser.add_argument(
            "-h",
            "--help",
            action="store_true",
            help="Print help message.",
        )
        self.run_parser.add_argument(
            "--pdb",
            action="store_true",
            default=False,
            help="enter pdb debuggin on error",
        )
        self.run_parser.add_argument(
            "node_name",
            nargs="?",
            type=str,
            default="",
            help="enter pdb debuggin on error",
        )
        self.run_parser.add_argument(
            "--config",
            type=str,
            default=None,
            help="path to a config file containing the node's parameters.",
        )
        self.run_parser.add_argument(
            "--env",
            type=str,
            default=None,
            help="path to an enviroment file containing the B2 configuration.",
        )
        self.run_parser.set_defaults(func=self.run)

    def help(self) -> None:
        print("Here is a list with all available actions:", file=sys.stderr)
        print("   run      Runs a node", file=sys.stderr)
        print("   list     List all avialbe nodes", file=sys.stderr)

    def print_no_action(self) -> None:
        print("Error, no action was given!", file=sys.stderr)
        print(
            f"Use `{self.argv[0]} help` to print a list of available actions.",
            file=sys.stderr,
        )

    def get_node(self, node_name: str) -> type[Node[ARGS, T]]:
        matched_nodes = []
        if "." in node_name:
            for node in self.nodes:
                if f"{node.__module__}.{node.__qualname__}" == node_name:
                    matched_nodes.append(node)
        else:
            for node in self.nodes:
                if node.__qualname__ == node_name:
                    matched_nodes.append(node)

        if len(matched_nodes) == 0:
            print(f"Did not found a Node with name: `{node_name}`")
        if len(matched_nodes) > 1:
            print(f"Found multiple Nodes with name: `{node_name}`")

        return matched_nodes[0]

    def run(self):

        if self.args.help:
            if self.args.node_name == "":
                self.run_parser.print_help()
                sys.exit()
            else:
                # print the help message of the node
                self.unknown_args.append("--help")

        node_name = self.args.node_name
        node_args = self.argv[self.argv.index(node_name) + 1 :]
        node_cls = self.get_node(node_name)

        with utils.pdb_post_mortem(self.args.pdb):

            if self.env_file is None and self.args.env is None:
                env_file = env.find_enviroment_file(
                    env.infer_project_dir(self.package)
                )
            elif self.env_file is None and self.args.env is not None:
                env_file = self.args.env
            else:
                env_file = self.env_file

            # if config is set and

            read_config_from_file = False

            if self.args.config is not None:
                # --config flag given but after node?
                read_config_from_file = self.argv.index(
                    "--config"
                ) < self.argv.index(node_name)

            if read_config_from_file:
                if len(self.unknown_args) != 0:
                    raise ValueError(
                        "Got both config file and also some arguments.\n"
                        f"Config file: {self.args.config}\n"
                        f"Arguments: {self.unknown_args}\n"
                    )
                node_args = anyconfig.load(self.args.config)
                created_node: Node[ARGS, T] = node_mod.create_node(
                    node_cls, node_args, env_file
                )
            else:
                created_node: Node[ARGS, T] = node_mod.create_node(
                    node_cls, node_args, env_file
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

    def list(self):
        cls_names = [
            f"{cls.__module__}.{cls.__qualname__}" for cls in self.nodes
        ]
        cls_length = max(len(cls_name) for cls_name in cls_names)
        print("")
        print("Found the following executable nodes:")
        for cls_name, cls in zip(cls_names, self.nodes):
            first_doc_line = (cls.__doc__ or "[no docstring]").split("\n")[0]
            print(f"    {cls_name.ljust(cls_length)}  - {first_doc_line}")

        print("")
        print("For more information on each analysis execute:")
        print(f"     python -m <your_package> run {cls_names[-1]} --help")
        sys.exit(0)

    def __call__(self) -> Optional[tuple[Node[ARGS, T], T]]:
        if not self.argv or self.argv[0] in ["-h", "help", "--help"]:
            self.help()
            return None

        self.args, self.unknown_args = self.parser.parse_known_args(self.argv)
        return self.args.func()


def run_main(
    package: str,
    env_file: Optional[io.PATH_LIKE] = None,
    argv: Optional[list[str]] = None,
) -> Optional[tuple[Node[ARGS, T], T]]:
    runner = MainRunner(package, env_file, argv)
    return runner()
