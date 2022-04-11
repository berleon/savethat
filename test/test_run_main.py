import dataclasses
from pathlib import Path
from typing import Optional, cast

from phd_flow import node as node_mod
from phd_flow import run_main


@dataclasses.dataclass(frozen=True)
class ConfigTestArgs(node_mod.Args):
    config: str


class ConfigTest(node_mod.Node[ConfigTestArgs, str]):
    def _run(self) -> str:
        return self.args.config


def test_run_main(env_file: Path):
    result = cast(
        Optional[tuple[ConfigTest, str]],
        run_main(
            "test",
            env_file=env_file,
            argv=[
                "run",
                "test.test_run_main.ConfigTest",
                "--config",
                "my_config_file",
            ],
        ),
    )
    assert result is not None
    assert result[1] == "my_config_file"
