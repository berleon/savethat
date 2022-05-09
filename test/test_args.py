import dataclasses

import pytest

import savethat


@dataclasses.dataclass(frozen=True)
class MyArgs(savethat.Args):
    name: str
    n_times: int


def test_init_of_args():
    args_init = MyArgs(name="Bodo", n_times=10)
    args_parsed = MyArgs.parse_args(["--name", "Bodo", "--n_times", "10"])
    assert args_init == args_parsed


class NoDataclassArgs(savethat.Args):
    name: str
    n_times: int


def test_no_dataclass_raises():
    with pytest.raises(TypeError):
        NoDataclassArgs.parse_args(["--name", "Bodo", "--n_times", "10"])
