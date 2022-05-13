from pathlib import Path

import pytest

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
