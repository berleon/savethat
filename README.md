# savethat

This library to provide a straightforward way to save your ML experiments.
I wish I would have written this library before my PhD and not at the end.
`savethat` is specifically addressed for PhD students: limited budget, various compute
infrastructure (SLURM, servers), little time to spend on setup.

This library provides the following things:

* Simple way to create nodes executable from CLI
* Each node has an unique output directory which is synced to [Backblaze B2]
* A CLI to administer the remote storage
* The command line arguments are parsed by [typed-argument-parser]
* Reproducable experiments by [reproducible]
* Logging by [loguru]

The main goal is to provide the necessary infrastructure to write reproducible
research code. You can use this library with any DL framework.

## Template Setup

The recommended way to use `savethat` is to use the [cookiecutter template](https://github.com/berleon/savethat_cookiecutter). The template creates a new project with pre-configured tools such as flake8, pytest, tox, mypy, Github Actions.

```bash
$ project='my_project'
$ mkdir -p $project && cd $project
$ python3 -m venv venv && source venv/bin/activate
$ pip install -U pip wheel setuptools cookiecutter poetry
$ cookiecutter https://github.com/berleon/savethat_cookiecutter
```

See this **[Tutorial]** for a complete description of the setup process.

## Manual Setup

First, create a config file with the B2 credentials:
```toml
# the data will be stored at this location
local_path="${PROJECT_ROOT}/data_storage"

# the B2 Key
b2_key_id="XXXXXXXXXXX"
b2_key="XXXXXXXXXXX"
# name of the B2 bucket
b2_bucket="my-b2-bucket"
# prefix for this project
b2_prefix="my_project"
```
You can signup at [B2 Cloud Storage](https://www.backblaze.com/b2/docs/quick_account.html).

The next step is to make your project runnable by adding `my_project/__main__.py`:

```python
from pathlib import Path

import savethat

if __name__ == "__main__":
    repro_dir = Path(__file__).parent.parent

    savethat.run_main(
        "my_project",
        env_file=repro_dir / "savethat.toml",
    )

```
Suppose you created a subclass `FitOLS` of `savethat.Node` in the file `my_project/fit_ols.py`,
then you could list the node:
```bash
$ python -m fitols nodes
Found the following executable nodes:
    my_project.fit_ols.FitOLS  - [no docstring]

For more information on each analysis execute:
     python -m my_project run my_project.fit_ols.FitOLS --help
```

## Overview

### How to run a node?

Simply run:
```bash
python -m my_project run my_project.fit_ols.FitOLS --my-args
```

### What is saved when a Node is run?

The following files are saved as default:
```
args.json           # arguments of the node
output.jsonl        # log of the run in jsonl format
output.log          # log of the run in text format
reproducible.json   # reproducibility information
results.pickle      # results of the run
```

### How to save more files?

Each node, has a reference to a storage parameter:
```
@dataclasses.dataclass(frozen=True)
class MyNodeArgs:
    dataset: str

class MyNode(savethat.Node[MyNodeArgs, str]):
    def _run(self):
        self.storage.download(self.args.dataset)
        with open(self.storage / self.args.dataset / "data.csv") as f:
            ...

        self.storage.upload(self.args.dataset / "results.csv")
```

See the [Storage API Docs] for more information.

### Logging

`savethat` uses [loguru](https://github.com/Delgan/loguru). You can import
a preconfigured logger using `from savethat import logger`. See
[loguru's documentation](https://loguru.readthedocs.io/en/stable/index.html)
for more details.

### How to list past runs?

To list all past runs:
```
python -m {{ cookiecutter.pkg_name }} ls
```

You can also select only runs starting with `FitOLS` that were completed
successfully in the last 3 hours:
```
python -m {{ cookiecutter.pkg_name }} ls FitOLS --completed --last 3h
```

You can also get the runs information from python:

```
get_storage('savethat.toml').find_runs(
    'FitOLS',
    only_completed=True,
    after=datetime.now(timezone.utc) - timedelta(hours=3),  # all times are in utc
)
```

### Delete runs

All failed runs from the last 3 hours can be deleted with:

```
python -m {{ cookiecutter.pkg_name }} rm FitOLS --failed --last 3h
```
The CLI would ask for confirmation before deleting all completed runs in the last 3 hours.
You can use the `--force` flag to skip the confirmation.
See `python -m {{ cookiecutter.pkg_name }} rm  --help ` for more information.


#### What is missing?

* Chaining nodes is currently not possible really supported.
* Running nodes in an isolated container is currently not possible.
* The code is tested on Mac OS X and Linux, but not on Windows.


[Tutorial]: https://github.com/berleon/savethat_cookiecutter/blob/master/docs/tutorial.md
[Storage API Docs]: https://berleon.github.io/savethat/savethat/io.html
[reproducible]: https://github.com/oist-cnru/reproducible
[Backblaze B2]: https://www.backblaze.com/
[loguru]: https://github.com/Delgan/loguru
[typed-argument-parser]: https://github.com/swansonk14/typed-argument-parser
