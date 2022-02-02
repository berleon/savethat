from __future__ import annotations

import argparse
import sys
from typing import Optional, TypeVar

import anyconfig
from loguru import logger
from phd_flow.node import Node

from phd_flow import args, config, io, log
from phd_flow import node as node_mod
from phd_flow import utils

ARGS = TypeVar("ARGS", bound="args.Args")
T = TypeVar("T")


class MainRunner:
    def __init__(
        self,
        package: str,
        config_file: Optional[io.PATH_LIKE] = None,
        argv: Optional[list[str]] = None,
    ):
        if config_file is not None:
            self.config_file = config_file
        else:
            self.config_file = config.find_config_file(
                config.guess_project_dir(package)
            )
        utils.import_submodules(package)
        self.nodes = {cls.__qualname__: cls for cls in Node.__subclasses__()}

        if argv is None:
            self.argv = sys.argv[1:]
        else:
            self.argv = argv

        self.parser = self.create_parser()

    def create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()
        parser.set_defaults(func=self.help)
        subparsers = parser.add_subparsers()

        list = subparsers.add_parser("list")
        list.set_defaults(func=self.list)

        # create the parser for the "bar" command
        run = subparsers.add_parser("run")
        run.add_argument(
            "--pdb",
            action="store_true",
            default=False,
            help="enter pdb debuggin on error",
        )
        run.add_argument(
            "node_name", nargs=1, type=str, help="enter pdb debuggin on error"
        )
        run.add_argument(
            "--config", type=str, default=None, help="path to a config file"
        )
        run.set_defaults(func=self.run)
        return parser

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

    def run(self):
        node_name = self.args.node_name[0]
        node_cls: type[Node[ARGS, T]] = self.nodes[node_name]  # type: ignore

        with utils.pdb_post_mortem(self.args.pdb):

            if self.args.config is not None:
                if len(self.unknown_args) != 0:
                    raise ValueError(
                        "Got both config file and also some arguments.\n"
                        f"Config file: {self.args.config}\n"
                        f"Arguments: {self.unknown_args}\n"
                    )
                node_args = anyconfig.load(self.args.config)
                created_node: Node[ARGS, T] = node_mod.create_node(
                    node_cls, self.config_file, args_dict=node_args
                )
            else:
                created_node: Node[ARGS, T] = node_mod.create_node(
                    node_cls, self.config_file, self.unknown_args
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
        for name, node in self.nodes.items():
            print(f"{name}:             {node.__module__}")
            print(node.__doc__)

    def __call__(self) -> Optional[tuple[Node[ARGS, T], T]]:
        if not self.argv or self.argv[0] in ["-h", "help", "--help"]:
            self.help()
            return None

        self.args, self.unknown_args = self.parser.parse_known_args(self.argv)
        return self.args.func()


def run_main(
    package: str,
    config_file: Optional[io.PATH_LIKE] = None,
    argv: Optional[list[str]] = None,
) -> Optional[tuple[Node[ARGS, T], T]]:
    runner = MainRunner(package, config_file, argv)
    return runner()
