import subprocess
from pathlib import Path


def test_main(tmp_path: Path, config_file: Path):
    p = subprocess.Popen(
        [
            "python",
            "-m",
            "test.test_package",
            "run",
            "FitOLS",
            "--dataset",
            "./test/data/california_tiny.csv",
            "--target",
            "MedHouseVal",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = p.communicate()
    stdout = stdout_bytes.decode("utf-8")

    print("-" * 80)
    print(stdout)
    print("-" * 80)

    print("-" * 80)
    print(stderr_bytes.decode("utf-8"))
    print("-" * 80)

    assert "Finished" in stdout

    out_part = stdout[stdout.index("'output_dir'") + len("'output_dir': '") :]
    output_dir = Path(out_part[: out_part.index("'")])
    assert (output_dir / "results.pickle").exists()
