from pathlib import Path
from typing import Any

import pytest

import savethat
from savethat import io


@pytest.fixture
def storage(tmp_path: Path) -> io.B2Storage:
    fake_b2 = io.SimulatedB2API()
    return io.B2Storage(
        local_path=tmp_path,
        remote_path=Path("test"),
        b2_bucket=fake_b2.bucket_name,
        b2_key_id=fake_b2.application_key_id,
        b2_key=fake_b2.master_key,
        _bucket=fake_b2.bucket,
    )


@pytest.fixture
def env_file() -> Path:
    test_dir = Path(__file__).parent
    return test_dir / "test_env.toml"


@pytest.fixture
def env(env_file: Path) -> dict[str, Any]:
    savethat.set_project_dir(Path(__file__).parent.parent)
    return savethat.env.read_env_file(env_file)
