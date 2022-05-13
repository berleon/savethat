# savethat - Save your ML experiments in one place

The main goal of `savethat` is to provide the necessary infrastructure to write reproducible
research code. You can use this library with any DL framework.

This library provides the following things:

* Saves your experiments arguments and results.
* Simple way to create executable nodes.
* A CLI interface to start and list experiments.

`savethat` was built for PhD students: limited budget, various compute infrastructure (SLURM, servers), little time to spend for the setup.

This library is mostly a wrapper around the following libraries:

* [b2] to sync your files to [Backblaze B2].
* [typed-argument-parser] to parse the command line arguments.
* [reproducible] to save your currently installed packages and git state.
* [loguru] to log messages.


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

In case you want to add `savethat` to an existing project, you have to call the `savethat` command line interface. The easist way is to add the following to your `./your_package/__main__.py` file:

```python
from pathlib import Path

import savethat

if __name__ == "__main__":
    repro_dir = Path(__file__).parent.parent

    savethat.run_main("my_project")

```

You can now invoke it with `python -m your_package`.
Suppose you created a subclass `FitOLS` of `savethat.Node` in the file `my_project/fit_ols.py`,
then you could list the node:
```bash
$ python -m my_project nodes
Found the following executable nodes:
    my_project.fit_ols.FitOLS  - [no docstring]

For more information on each analysis execute:
     python -m my_project run my_project.fit_ols.FitOLS --help
```


### Exemplary Node

This is an example how to implemented an executable node:

```python
import dataclasses
import pickle
from typing import Any

import pandas as pd
import savethat
from savethat import logger

...


@dataclasses.dataclass(frozen=True)
class FitOLSArgs(savethat.Args):
    dataset: str  # path to csv dataset
    target: str  # column name of the target


@dataclasses.dataclass(frozen=True)
class FitOLSResult:
    mse: float
    params: dict[str, Any]


class FitOLS(savethat.Node[FitOLSArgs, FitOLSResult]):
    def _run(self) -> FitOLSResult:
        # Loading the data
        if self.args.dataset == "california_housing":
            cali_df = sklearn.datasets.fetch_california_housing(as_frame=True)
            df = cali_df.data
            df['MedHouseVal'] = cali_df.target

            ...

        else:
            df = pd.read_csv(self.args.dataset)


        with self.storage.open(f"datasets.pickle", "wb") as f:
            pickle.dump((X_train, X_test, y_train, y_test), f)

        self.storage.upload(dataset_key)

        ols = sklearn.linear_model.LinearRegression()

        ...

        # the results will be stored to `self.key / results.pickle`
        return FitOLSResult(mse, ols.get_params())
```

For a full example, see [the fitols repository].

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
python -m my_project ls
```

You can also select only runs starting with `FitOLS` that were completed
successfully in the last 3 hours:
```
python -m my_project ls FitOLS --completed --last 3h
```

You can also get the runs information from python:

```

savethat.get_storage('my_project').find_runs(
    'FitOLS',
    only_completed=True,
    after=datetime.now(timezone.utc) - timedelta(hours=3),  # all times are in utc
)
```


### Delete runs

All failed runs from the last 3 hours can be deleted with:

```
python -m my_project rm FitOLS --failed --last 3h
```
The CLI would ask for confirmation before deleting all completed runs in the last 3 hours.
You can use the `--force` flag to skip the confirmation.
See `python -m my_project rm  --help ` for more information.


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
[b2]: https://github.com/Backblaze/b2-sdk-python
[the fitols repository]: https://github.com/berleon/fitols
