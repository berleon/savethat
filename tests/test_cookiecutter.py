import os
import subprocess
from pathlib import Path

from cookiecutter.main import cookiecutter


def test_cookie_template(tmp_path: Path) -> None:
    # Create project from the cookiecutter-pypackage/ template
    cookiecutter(
        "https://github.com/berleon/savethat_cookiecutter",
        checkout=os.environ.get("SAVETHAT_COOKIECUTTER_BRANCH", "master"),
        extra_context={"project_name": "test_template"},
        no_input=True,
        output_dir=tmp_path,
    )
    project_dir = tmp_path / "test_template"

    assert project_dir.is_dir()

    this_dir = Path(__file__).parent
    savethat_dir = this_dir.parent.absolute()
    proc = subprocess.Popen(
        [str(this_dir / "test_template.sh"), str(savethat_dir)],
        cwd=str(project_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert proc.stdout is not None

    while proc.poll() is None:
        print(proc.stdout.readline().decode("utf-8"), end="")

    assert proc.returncode == 0
