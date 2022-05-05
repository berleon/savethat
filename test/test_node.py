import dataclasses
import random
from typing import Any

from phd_flow import io
from phd_flow import node as node_mod


@dataclasses.dataclass(frozen=True)
class SampleIntArgs(node_mod.Args):
    max: int


class SampleInt(node_mod.Node[SampleIntArgs, int]):
    def _run(self) -> int:
        number = random.randint(0, self.args.max)
        with self.storage.open(self.output_dir / "result.txt", "w") as f:
            f.write(str(number))
        print("Upload key", self.key)
        self.storage.upload(self.key)
        return number


@dataclasses.dataclass(frozen=True)
class PrintArgs(node_mod.Args):
    key_to_print: str
    n_times: int = 10


class Print(node_mod.Node[PrintArgs, None]):
    def _run(self) -> None:
        with self.storage.open(self.args.key_to_print, "r") as f:
            print(f.read())


def test_run_node(storage: io.Storage, env: dict[str, Any]) -> None:
    args = SampleIntArgs(max=10)
    # storage.remove("test_sample_int", remote=True)

    node = SampleInt("test_sample_int", storage, args, env)
    result = node.run()
    assert result <= 10

    assert isinstance(storage, io.B2Storage)
    print("remote files", list(storage.bucket.ls()))

    files = [str(file) for file in storage.remote_ls("test_sample_int")]

    assert "test_sample_int/result.txt" in files


def test_run_pipeline(storage: io.Storage, env: dict[str, Any]) -> None:
    pipeline = node_mod.join(
        SampleInt,
        Print,
        lambda s, i: PrintArgs(key_to_print=str(s.output_dir / "result.txt")),
    )
    args = SampleIntArgs(max=20)

    pipeline("test_pipeline", storage, args, env).run()
