import subprocess
from pathlib import Path


def test_main(tmp_path: Path, env_file: Path):
    commands = [
        (
            f"python -m test.test_package.my_package run --env {env_file} "
            "--config test/test_package/run_config.json FitOLS"
        ),
        (
            f"python -m test.test_package.my_package run --env {env_file} "
            "FitOLS --dataset ./test/data/california_tiny.csv"
            " --target MedHouseVal"
        ),
    ]
    for command in commands:
        print(f"Executing: {command}")
        p = subprocess.Popen(
            command.split(" "),
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

        out_part = stdout[
            stdout.index("'output_dir'") + len("'output_dir': '") :
        ]
        output_dir = Path(out_part[: out_part.index("'")])
        assert (output_dir / "results.pickle").exists()