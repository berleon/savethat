import random
from pathlib import Path

from phd_flow import io
from phd_flow import node as node_mod


class SampleIntArgs(node_mod.Args):
    max: int


class SampleInt(node_mod.Node[SampleIntArgs, int]):
    def _run(self) -> int:
        number = random.randint(0, self.args.max)
        with self.storage.open(self.key / "result.txt", "w") as f:
            f.write(str(number))
        print("Upload key", self.key)
        self.storage.upload(self.key)
        return number


class PrintArgs(node_mod.Args):
    key_to_print: str
    n_times: int = 10


class Print(node_mod.Node[PrintArgs, None]):
    def _run(self) -> None:
        with self.storage.open(self.args.key_to_print, "r") as f:
            print(f.read())


def test_run_node(storage: io.Storage):
    args = SampleIntArgs()
    args.from_dict(dict(max=10))
    storage.remove("test_sample_int", remote=True)
    node = SampleInt("test_sample_int", storage, args)
    assert node.run() <= 10

    files = list(storage.remote_ls("test_sample_int"))
    assert Path("/test_sample_int/result.txt") in files


def test_run_pipeline(storage: io.Storage):
    pipeline = node_mod.join(
        SampleInt,
        Print,
        lambda s, i: PrintArgs().from_dict(
            dict(key_to_print=s.key / "result.txt")
        ),
    )
    args = SampleIntArgs()
    args.from_dict(dict(max=20))
    pipeline("test_pipeline", storage, args).run()
