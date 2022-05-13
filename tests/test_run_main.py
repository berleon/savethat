import contextlib
import dataclasses
import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Iterator, Optional, cast

import pytest
import toml

import savethat
from savethat import env
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
    credential_file: PATH_LIKE,
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
    ] = savethat.run_main(package, credential_file, argv=argv)
    print("-" * 80)
    return result


def run_node(credential_file: PATH_LIKE) -> tuple[ConfigTest, str]:
    return cast(
        tuple[ConfigTest, str],
        run_main(
            "test_run_main",
            credential_file,
            argv=[
                "run",
                "test_run_main.ConfigTest",
                "--config",
                "my_config_file",
            ],
        ),
    )


@pytest.fixture
def credential_file(tmp_path: Path) -> Path:
    filename = tmp_path / "credential_file.toml"

    env.store_credentials(
        "test_run_main",
        env.B2Credentials.no_syncing(local_path=tmp_path / "data_storage"),
        filename,
    )
    return filename


def test_main_run(credential_file: Path) -> None:
    result = run_node(credential_file)
    assert result is not None
    assert result[1] == "my_config_file"


def test_main_help(credential_file: Path) -> None:
    f = io.StringIO()
    with redirect_stdout(f), redirect_stderr(f):
        run_main(
            "test_run_main",
            credential_file,
            argv=[
                "--help",
            ],
        )

    assert "Here is a list with all available actions:" in f.getvalue()


def test_main_node_help(credential_file: Path) -> None:
    f = io.StringIO()
    with redirect_stdout(f), redirect_stderr(f), pytest.raises(SystemExit):
        run_main(
            "test_run_main",
            credential_file,
            argv=[
                "run",
                "test_run_main.ConfigTest",
                "--help",
            ],
        )

    assert "--my_very_special_flag" in f.getvalue()


def test_main_nodes(credential_file: Path) -> None:
    f = io.StringIO()
    with redirect_stdout(f):
        run_main(
            "test_run_main",
            credential_file,
            argv=[
                "nodes",
            ],
        )
    out = f.getvalue()
    assert "test_run_main.ConfigTest" in out


def test_main_ls(credential_file: Path) -> None:
    run_node(credential_file)

    f = io.StringIO()
    with redirect_stdout(f), redirect_stderr(f):
        run_main(
            "test_run_main",
            credential_file,
            argv=["ls", "--local"],
        )
    out = f.getvalue()
    print(out)
    assert "ConfigTest" in out


def test_main_ls_last(credential_file: Path) -> None:
    run_node(credential_file)

    f = io.StringIO()
    with redirect_stdout(f), redirect_stderr(f):
        run_main(
            "test_run_main",
            credential_file,
            argv=["ls", "--local", "--last", "3h"],
        )
    out = f.getvalue()
    assert "ConfigTest" in out
    print(out)


@contextlib.contextmanager
def replace_stdin(target: io.StringIO) -> Iterator[None]:
    orig = sys.stdin
    sys.stdin = target
    yield
    sys.stdin = orig


def as_inputs(*s: str) -> io.StringIO:
    return io.StringIO("\n".join(s) + "\n\n")


def test_setup_credentials_no_syncing(tmp_path: Path) -> None:
    not_existing_credentials = tmp_path / "credentials.toml"

    answers = as_inputs(
        "n",  # no remote syncing
        str(tmp_path / "my_local_path"),
    )

    f = io.StringIO()
    with redirect_stdout(f), redirect_stderr(f), replace_stdin(answers):
        run_main(
            "test_run_main",
            credential_file=not_existing_credentials,
            argv=["setup_b2"],
        )

    print(f.getvalue())
    assert not_existing_credentials.exists()

    with open(not_existing_credentials) as fc:
        cred = toml.load(fc)

    assert "test_run_main" in cred
    assert cred["test_run_main"]["local_path"] == str(
        tmp_path / "my_local_path"
    )
    assert cred["test_run_main"]["skip_syncing"]


def test_setup_credentials_with_syncing(tmp_path: Path) -> None:
    not_existing_credentials = tmp_path / "credentials.toml"

    answers = as_inputs(
        "y",  # yes remote syncing
        "my_key_id",
        "key",
        "my_bucket_name",
        "remote_prefix",
        str(tmp_path / "my_local_path"),
    )

    f = io.StringIO()
    with redirect_stdout(f), redirect_stderr(f), replace_stdin(answers):
        run_main(
            "test_run_main",
            credential_file=not_existing_credentials,
            argv=["setup_b2"],
        )

    print(f.getvalue())
    assert not_existing_credentials.exists()

    with open(not_existing_credentials) as fc:
        all_cred = toml.load(fc)

    assert "test_run_main" in all_cred
    cred = env.B2Credentials(**all_cred["test_run_main"])
    assert cred.b2_key_id == "my_key_id"
    assert cred.b2_key == "key"
    assert cred.b2_bucket == "my_bucket_name"
    assert cred.remote_path == "remote_prefix"
    assert cred.local_path == str(tmp_path / "my_local_path")
    assert not cred.skip_syncing


if __name__ == "__main__":
    test_dir = Path(__file__).parent.absolute()
    sys.path.append(str(test_dir))

    test_dir = Path(__file__).parent
    cred_file = test_dir / "savethat.toml"

    env.store_credentials(
        "test_run_main",
        env.B2Credentials.no_syncing(local_path=test_dir / "data_storage"),
        cred_file,
    )

    savethat.run_main("test_run_main", cred_file)
