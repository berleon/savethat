from pathlib import Path

import pytest

from phd_flow import config, io


@pytest.fixture
def storage(tmp_path: Path) -> io.B2Storage:
    fake_b2 = io._SimulatedB2API()
    return io.B2Storage(
        local_path=tmp_path,
        remote_path=Path("test"),
        b2_bucket=fake_b2.bucket_name,
        b2_key_id=fake_b2.application_key_id,
        b2_key=fake_b2.master_key,
        _bucket=fake_b2.bucket,
    )


@pytest.fixture
def config_file() -> Path:
    return config.guess_project_dir() / "test" / "config.toml"
