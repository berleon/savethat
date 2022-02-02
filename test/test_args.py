import dataclasses

import pytest

import phd_flow


@dataclasses.dataclass
class MyArgs(phd_flow.Args):
    name: str
    n_times: int


def test_init_of_args():
    args_init = MyArgs(name="Bodo", n_times=10)
    args_parsed = MyArgs.parse_args(["--name", "Bodo", "--n_times", "10"])
    assert args_init == args_parsed


class NoDataclassArgs(phd_flow.Args):
    name: str
    n_times: int


def test_no_dataclass_raises():
    with pytest.raises(TypeError):
        NoDataclassArgs.parse_args(["--name", "Bodo", "--n_times", "10"])
