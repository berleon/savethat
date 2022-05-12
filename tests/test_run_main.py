import dataclasses
import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Optional, cast

import pytest

import savethat
from savethat import node as node_mod
from savethat.io import PATH_LIKE


@dataclasses.dataclass(frozen=True)
class ConfigTestArgs(node_mod.Args):
    config: str
    my_very_special_flag: bool = False


class ConfigTest(node_mod.Node[ConfigTestArgs, str]):
    def _run(self) -> str:
        return self.args.config


def run_main(
    package: str,
    env_file: PATH_LIKE,
    argv: list[str] = [],
) -> Optional[tuple[savethat.Node[savethat.ARGS, Any], Any]]:
    test_dir = Path(__file__).parent.absolute()
    # Appending path to make file a package
    sys.path.append(str(test_dir))
    print("-" * 80)

    print(f"Running {package} with args: {' '.join(argv)}")
    print()
    result: Optional[
        tuple[savethat.Node[savethat.ARGS, Any], Any]
    ] = savethat.run_main(package, env_file=env_file, argv=argv)
    print("-" * 80)
    return result


def run_node(env_file: Path) -> tuple[ConfigTest, str]:
    return cast(
        tuple[ConfigTest, str],
        run_main(
            "test_run_main",
            env_file=env_file,
            argv=[
                "run",
                "test_run_main.ConfigTest",
                "--config",
                "my_config_file",
            ],
        ),
    )


def test_main_run(env_file: Path) -> None:
    result = run_node(env_file)
    assert result is not None
    assert result[1] == "my_config_file"


def test_main_help(env_file: Path) -> None:
    f = io.StringIO()
    with redirect_stdout(f), redirect_stderr(f):
        run_main(
            "test_run_main",
            argv=[
                "--help",
            ],
            env_file=env_file,
        )

    assert "Here is a list with all available actions:" in f.getvalue()


def test_main_node_help(env_file: Path) -> None:
    f = io.StringIO()
    with redirect_stdout(f), redirect_stderr(f), pytest.raises(SystemExit):
        run_main(
            "test_run_main",
            argv=[
                "run",
                "test_run_main.ConfigTest",
                "--help",
            ],
            env_file=env_file,
        )

    assert "--my_very_special_flag" in f.getvalue()


def test_main_nodes(env_file: Path) -> None:
    test_dir = Path(__file__).parent.absolute()
    sys.path.append(str(test_dir))

    f = io.StringIO()
    with redirect_stdout(f):
        run_main(
            "test_run_main",
            argv=[
                "nodes",
            ],
            env_file=env_file,
        )
    out = f.getvalue()
    assert "test_run_main.ConfigTest" in out


def test_main_ls(env_file: Path) -> None:
    run_node(env_file)

    f = io.StringIO()
    with redirect_stdout(f), redirect_stderr(f):
        run_main(
            "test_run_main",
            argv=["ls", "--local"],
            env_file=env_file,
        ),
    out = f.getvalue()
    print(out)


if __name__ == "__main__":
    test_dir = Path(__file__).parent.absolute()
    sys.path.append(str(test_dir))

    test_dir = Path(__file__).parent
    env_file = test_dir / "test_env.toml"

    savethat.run_main("test_run_main", env_file)
