import getpass
import os
import subprocess
from pathlib import Path

import pytest
from cookiecutter.main import cookiecutter

from savethat import env


@pytest.fixture
def template_dir(tmp_path: Path) -> Path:
    # pytest-{run_id}
    pytest_number = tmp_path.parts[-2]
    number = pytest_number.split("-")[-1]

    tmp = Path(os.getenv("TMPDIR", "/tmp"))

    user = getpass.getuser()
    return tmp / f"savethat-cookiecutter-of-{user}" / f"template-{number}"


def test_cookie_template(tmp_path: Path, template_dir: Path) -> None:
    # Create project from the cookiecutter-pypackage/ template

    location = os.environ.get(
        "SAVETHAT_COOKIECUTTER_LOCATION",
        "https://github.com/berleon/savethat_cookiecutter",
    )
    branch = os.environ.get("SAVETHAT_COOKIECUTTER_BRANCH", "master")
    print(f"Testing against template: {location}@{branch}")

    cookiecutter(
        location,
        checkout=branch,
        extra_context={
            "project_name": "test_template",
            "_collect_coverage": "y",
        },
        no_input=True,
        output_dir=template_dir,
    )
    print(f"Template created in {template_dir}")
    project_dir = template_dir / "test_template"

    assert project_dir.is_dir()

    this_dir = Path(__file__).parent
    savethat_dir = this_dir.parent.absolute()

    credential_file = tmp_path / "credentails.toml"

    env.store_credentials(
        "test_template",
        env.B2Credentials.no_syncing(tmp_path / "data_storage"),
        credential_file,
    )

    proc = subprocess.Popen(
        [
            str(this_dir / "run_tests_of_cookiecutter_template.sh"),
            str(savethat_dir),
            str(credential_file),
        ],
        cwd=str(project_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert proc.stdout is not None

    while proc.poll() is None:
        print(proc.stdout.readline().decode("utf-8"), end="")

    print(f"Template was renderd to {template_dir}")
    assert proc.returncode == 0
