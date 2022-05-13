from __future__ import annotations

import argparse
import datetime
import inspect
import sys
from pathlib import Path
from typing import Any, Iterator, Optional, TypeVar, Union

import anyconfig

from savethat import args, env, io, log, logger
from savethat import node as node_mod
from savethat import utils
from savethat.node import Node

ARGS = TypeVar("ARGS", bound="args.Args")
T = TypeVar("T")


class MainRunner:
    def __init__(
        self,
        package: str,
        credential_file: Optional[io.PATH_LIKE] = None,
        argv: Optional[list[str]] = None,
        project_dir: Optional[io.PATH_LIKE] = None,
    ):
        if argv is None:
            self.all_argv = sys.argv[1:]
        else:
            self.all_argv = argv

        self.setup_parser = argparse.ArgumentParser(add_help=False)
        self.setup_parser.add_argument(
            "--credentials",
            type=str,
            default=None,
            help="Path to the file with the B2 credentials.",
        )
        self.setup_parser.add_argument(
            "--debug",
            action="store_true",
            help="Print debug information.",
        )

        first_no_dash = min(
            (i for i, a in enumerate(self.all_argv) if not a.startswith("--")),
            default=len(self.all_argv),
        )

        setup_args = self.all_argv[:first_no_dash]
        if len(setup_args) > 0 and "--credentials" == setup_args[-1]:
            setup_args.append(self.all_argv[first_no_dash])
            self.argv = self.all_argv[first_no_dash + 1 :]
        else:
            self.argv = self.all_argv[first_no_dash:]

        self.setup_args, _ = self.setup_parser.parse_known_args(setup_args)

        if self.setup_args.debug:
            log.setup_logger(stderr_level="DEBUG")
        else:
            log.setup_logger(stderr_level="INFO")

        self.credential_file = credential_file or self.setup_args.credentials

        self.package = package

        if project_dir is not None:
            self.project_dir = Path(project_dir)
        else:
            self.project_dir = env.infer_project_dir(self.package)

        self.create_parser()

    @staticmethod
    def find_all_subclasses() -> list[type[Node]]:
        def all_subclasses(cls: type) -> set[type[Node]]:
            logger.debug(f"Scanning: {cls.__module__}.{cls.__qualname__}")
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

    def get_nodes(self) -> list[type[Node]]:
        utils.import_submodules(self.package, ignore_errors=False)
        return self.find_all_subclasses()

    def create_parser(
        self,
    ):

        # we need to use argparse as tap cannot handle subparsers properly.
        self.parser = argparse.ArgumentParser()
        self.parser.set_defaults(func=self.help)
        self.subparsers = self.parser.add_subparsers()

        # ---------------------------------------------------------------
        # nodes

        nodes_parser = self.subparsers.add_parser(
            "nodes", description="List all nodes."
        )
        nodes_parser.set_defaults(func=self.list_nodes)

        # ---------------------------------------------------------------
        # run

        self.run_parser = self.subparsers.add_parser(
            "run", description="Runs a node.", add_help=False
        )
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
        self.run_parser.set_defaults(func=self.run)

        # ---------------------------------------------------------------
        # setup_b2
        setup_b2_parser = self.subparsers.add_parser(
            "setup_b2", description="Setup B2 credentials.", add_help=True
        )
        setup_b2_parser.set_defaults(func=self.setup_b2)
        # ---------------------------------------------------------------
        # download

        download_parser = self.subparsers.add_parser(
            "download", description="Downloads a run from B2.", add_help=True
        )
        download_parser.set_defaults(func=self.download)
        download_parser.add_argument(
            "key",
            nargs=1,
            default="",
            help="Key to download.",
        )
        # ---------------------------------------------------------------
        # upload

        upload_parser = self.subparsers.add_parser(
            "upload", description="Uploads a run to B2.", add_help=True
        )
        upload_parser.set_defaults(func=self.upload)
        upload_parser.add_argument(
            "key",
            nargs=1,
            default="",
            help="Key to upload.",
        )
        # ---------------------------------------------------------------
        # ls

        self.ls_parser = self.subparsers.add_parser(
            "ls", description="List past runs.", add_help=True
        )
        self.ls_parser.set_defaults(func=self.ls)
        self.ls_parser.add_argument(
            "-r", "--recursive", help="Recursively list files."
        )
        self.ls_parser.add_argument(
            "--before", default=None, help="List outputs before this date."
        )
        self.ls_parser.add_argument(
            "--after", default=None, help="List outputs after this date."
        )
        self.ls_parser.add_argument(
            "--all",
            default=False,
            action="store_true",
            help="List all files of the runs.",
        )
        self.ls_parser.add_argument(
            "--failed",
            action="store_true",
            default=False,
            help="List only runs without results.",
        )
        self.ls_parser.add_argument(
            "--completed",
            action="store_true",
            default=False,
            help="List only runs with results.",
        )
        self.ls_parser.add_argument(
            "--local",
            default=False,
            action="store_true",
            help="List only locally stored runs.",
        )
        self.ls_parser.add_argument(
            "--last",
            default=None,
            help="Remove runs in the last minutes / hours / days, "
            "e.g. '1h' or '1d'. If no unit is specified, minutes are assumed.",
        )
        self.ls_parser.add_argument(
            "-a",
            "--absolute",
            action="store_true",
            help="Print absolute paths.",
        )
        self.ls_parser.add_argument(
            "path",
            nargs="?",
            default="",
            help="(Partial) path to search for outputs.",
        )

        # ---------------------------------------------------------------
        # rm

        self.rm_parser = self.subparsers.add_parser(
            "rm", description="Removes runs (local and remote).", add_help=False
        )
        self.rm_parser.add_argument(
            "-h", "--help", action="store_true", help="Print help message."
        )
        self.rm_parser.add_argument(
            "--failed",
            action="store_true",
            default=False,
            help="Remove runs without results.",
        )
        self.rm_parser.add_argument(
            "--local",
            action="store_true",
            default=False,
            help="Remove runs only locally.",
        )
        self.rm_parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Do not ask for confirmation.",
        )
        self.rm_parser.add_argument(
            "--dry",
            action="store_true",
            default=False,
            help="Do a dry run. Does not delete anything.",
        )
        self.rm_parser.add_argument(
            "--last",
            default=None,
            help="Remove runs in the last minutes / hours / days, "
            "e.g. '1h' or '1d'. If no unit is specified, minutes are assumed.",
        )
        self.rm_parser.add_argument(
            "--before", default=None, help="Remove runs before this date."
        )
        self.rm_parser.add_argument(
            "--after", default=None, help="Remove runs after this date."
        )
        self.rm_parser.add_argument(
            "path",
            nargs="?",
            default="",
            help="(Partial) path to search for outputs.",
        )
        self.rm_parser.set_defaults(func=self.rm)

    def get_credentials(
        self, credentials_file: Optional[io.PATH_LIKE]
    ) -> env.B2Credentials:
        try:
            return env.load_credentials(self.package, credentials_file)
        except (FileNotFoundError, KeyError):
            local_path = self.project_dir.parent / "data_storage"
            credentials = env.B2Credentials.no_syncing(local_path)
            logger.info(
                "No B2 credentials found. Not syncing to cloud! "
                "Run 'b2 setup' to set up credentials."
            )
            logger.info(f"Data will be stored in {local_path}.")
            env.store_credentials(self.package, credentials, credentials_file)
            return credentials

    def help(self) -> None:
        print("Here is a list with all available actions:", file=sys.stderr)
        for name, choice in self.subparsers.choices.items():
            print(f"    {name:<10} {choice.description}", file=sys.stderr)

    def print_no_action(self) -> None:
        print("Error, no action was given!", file=sys.stderr)
        print(
            f"Use `{self.argv[0]} help` to print a list of available actions.",
            file=sys.stderr,
        )

    def get_node(self, node_name: str) -> type[Node[ARGS, T]]:
        nodes = self.get_nodes()
        matched_nodes = []
        if "." in node_name:
            for node in nodes:
                if f"{node.__module__}.{node.__qualname__}" == node_name:
                    matched_nodes.append(node)
        else:
            for node in nodes:
                if node.__qualname__ == node_name:
                    matched_nodes.append(node)

        if len(matched_nodes) == 0:
            print(f"Did not found a Node with name: `{node_name}`")
        if len(matched_nodes) > 1:
            print(f"Found multiple Nodes with name: `{node_name}`")

        return matched_nodes[0]

    def _print_help_and_exit(self, parser: argparse.ArgumentParser) -> bool:
        if self.args.help:
            if self.args.node_name == "":
                parser.print_help()
                return True
            else:
                # print the help message of the node
                self.unknown_args.append("--help")
        return False

    def run(self) -> Union[None, tuple[Node, Any]]:
        if self._print_help_and_exit(self.run_parser):
            return None

        node_name = self.args.node_name
        node_args = self.argv[self.argv.index(node_name) + 1 :]
        node_cls: type[Node] = self.get_node(node_name)

        with utils.pdb_post_mortem(self.args.pdb):

            credentials_file = self.credential_file

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

            created_node: Node = node_mod.create_node(
                node_cls,
                node_args,
                credentials=self.get_credentials(credentials_file),
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

    def list_nodes(self) -> None:
        nodes = self.get_nodes()
        cls_names = [f"{cls.__module__}.{cls.__qualname__}" for cls in nodes]
        cls_length = max(len(cls_name) for cls_name in cls_names)
        print("")
        print("Found the following executable nodes:")
        for cls_name, cls in zip(cls_names, nodes):
            first_doc_line = (cls.__doc__ or "[no docstring]").split("\n")[0]
            print(f"    {cls_name.ljust(cls_length)}  - {first_doc_line}")

        print("")
        print("For more information on each analysis execute:")
        print(f"     python -m {self.package} run {cls_names[-1]} --help")

    def _ls_runs(
        self,
        storage: io.Storage,
        absolute: bool = False,
        local: bool = False,
    ) -> Iterator[tuple[Path, list[Path]]]:

        if self.args.before is not None:
            before = utils.parse_time(self.args.before)
        else:
            before = None

        last = getattr(self.args, "last")
        if last and self.args.after is not None:
            raise ValueError("Cannot use both --last and --after")
        if last is not None:
            unit = "m"
            if last[-1].lower() in "mhd":
                unit = last[-1].lower()
            if last[-1].lower() in "mhd":
                value = int(last[:-1])
            else:
                value = int(last)

            offset = {
                "m": datetime.timedelta(
                    minutes=value,
                ),
                "h": datetime.timedelta(hours=value),
                "d": datetime.timedelta(days=value),
            }[unit]
            after = datetime.datetime.now(datetime.timezone.utc) - offset
            d = after
            assert d.tzinfo is not None and d.tzinfo.utcoffset(d) is not None
        elif self.args.after is not None:
            after = utils.parse_time(self.args.after)
        else:
            after = None

        logger.debug(
            f"Finding runs in {storage / ''} with prefix {self.args.path}",
            remote=not local,
            only_failed=self.args.failed,
            only_completed=getattr(self.args, "completed", False),
            before=before,
            after=after,
        )
        yield from storage.find_run_files(
            self.args.path,
            remote=not local,
            only_failed=self.args.failed,
            only_completed=getattr(self.args, "completed", False),
            absolute=absolute,
            before=before,
            after=after,
        )

    def get_storage(self) -> io.Storage:
        credentials = self.get_credentials(self.credential_file)
        return io.B2Storage.from_credentials(credentials)

    def setup_b2(self) -> None:
        env.setup_credentials(
            self.project_dir, self.package, self.credential_file
        )

    def download(self):
        storage = self.get_storage()
        storage.download(self.args.key[0])

    def upload(self):
        storage = self.get_storage()
        storage.upload(self.args.key[0])

    def ls(self):
        storage = self.get_storage()

        for run, paths in self._ls_runs(
            storage, self.args.absolute, self.args.local
        ):
            if self.args.all:
                for path in paths:
                    print(str(path))
            else:
                print(str(run))

    def rm(self):
        storage = self.get_storage()

        if self.args.force:
            for run, _ in self._ls_runs(storage):
                storage.remove(run, local=True, remote=not self.args.local)
            return

        if self.args.local:
            local_tag = "LOCAL"
        else:
            local_tag = "both LOCAL and REMOTE"

        print(f"Would delete the following runs from {local_tag}:")
        print()
        n_runs = 0
        n_files = 0
        runs = []
        for run, files in self._ls_runs(storage):

            if self.args.local and not (storage / run).exists():
                continue
            print(str(run))
            n_runs += 1
            n_files += len(files)
            runs.append(run)

        if n_runs == 0:
            print("No matching runs found.")
            return

        print()
        print(f"Would delete {n_runs} runs with {n_files} files.")
        if self.args.dry:
            return

        print()
        print(
            f"Are you sure you want to DELETE these runs ({local_tag})? (y/n) ",
            end="",
        )
        answer = input().lower()
        print("")
        if answer != "y":
            print("Aborting.")
            return

        for run in runs:
            print(storage.remove.__code__)
            storage.remove(run, local=True, remote=not self.args.local)

    def __call__(self) -> Optional[tuple[Node[ARGS, T], T]]:
        if not self.argv or self.argv[0] in ["-h", "help", "--help"]:
            self.help()
            return None

        if self.argv[0] == "run":
            self.args, self.unknown_args = self.parser.parse_known_args(
                self.argv
            )
        else:
            self.args = self.parser.parse_args(self.argv)
            self.unknown_args = []
        return self.args.func()


def run_main(
    package: str,
    credential_file: Optional[io.PATH_LIKE] = None,
    argv: Optional[list[str]] = None,
) -> Optional[tuple[Node[ARGS, T], T]]:
    runner = MainRunner(package, credential_file, argv)
    return runner()
