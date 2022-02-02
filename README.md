# phd_flow -- MLOps for busy PhDs

A library to get at least some ordering into a ML PhD.
This library provides many useful things:

* Reproducable experiments
* Store results on Backblaze B2
* Logging


# Examples

This simple example shows how to use `phd_flow` for fitting an OLS.
This would go into `my_project/fit_ols.py`:

```python
import dataclasses
import pickle
from typing import Any

import pandas as pd
import sklearn
import sklearn.datasets
import sklearn.linear_model
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split

from phd_flow import logger, node


@dataclasses.dataclass
class FitOLSArgs(node.Args):
    dataset: str  # path to csv dataset
    target: str  # column name of the target


@dataclasses.dataclass
class FitOLSResult:
    mse: float
    params: dict[str, Any]


class FitOLS(node.Node[FitOLSArgs, FitOLSResult]):
    def _run(self) -> FitOLSResult:
        # Loading the data from storage
        df = pd.read_csv(self.args.dataset)
        # You can access any argument from `FitOLSArgs` with `self.args`
        train_keys = [k for k in df.keys() if k != self.args.target]
        X = df[train_keys].to_numpy()
        y = df[self.args.target].to_numpy()

        # A logger is preconfigured. Just `from phd_flow import logger`
        logger.info(f"Got {len(X)} samples.")
        X_train, X_test, y_train, y_test = train_test_split(X, y)

        # let's upload the dataset to the cloud
        dataset_key = "datasets" / self.key / "datasets.pickle"
        with self.storage.open(dataset_key, "wb") as f:
            pickle.dump((X_train, X_test, y_train, y_test), f)
        # the actual uploading
        self.storage.upload("datasets" / self.key)

        ols = sklearn.linear_model.LinearRegression()
        ols.fit(X_train, y_train)

        mse = mean_squared_error(y_test, ols.predict(X_test))
        logger.info(f"Mean squared error of {mse}")
        return FitOLSResult(mse, ols.get_params())
        # the results will be stored to `self.key / results.pickle`
```
Now, we make it runable by adding `my_project/__main__.py`:

```python
import phd_flow

phd_flow.run_main('my_project')
```


Finally, you have to create a configuration file (`config/default.toml`):

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

You can now execute the node with:
```sh
$ python -m my_project run FitOLS --dataset california.csv --target MedHouseVal
# Possible Output:
2022-02-01 16:13:04.180 | INFO     | phd_flow.io:from_file:127 - Loading config from file: test/config/default.toml
2022-02-01 16:13:04.192 | INFO     | phd_flow.log:setup_logger:34 - Use logger output_dir: test/data/FitOLS_2022-02-01T15:13:04.181832 - {}
2022-02-01 16:13:04.192 | INFO     | phd_flow.node:run:99 - Run Node - {'node': 'FitOLS', 'key': 'FitOLS_2022-02-01T15:13:04.181832', 'output_dir': test/data/FitOLS_2022-02-01T15:13:04.181832'}
```

A unique `key` is generated for each run. The default uses the time. The
returned value will be saved to `{key} / results.pickle`. After the run the
whole content of `{local_path}/{key}` will be uploaded to B2. `phd_flow` will
save the comandline arguments (`args.json`) and the logs  (`output.log`,
`output.json`).


# Install

For now use:

```sh
$ pip install git+https://github.com/berleon/phd_flow.git
```

# Concepts

## Storage

`phd_flow` currently only supports Backblaze B2.
You can signup at [B2 Cloud Storage](https://www.backblaze.com/b2/docs/quick_account.html).

Each node, has a reference to a storage parameter:
```
self.storage.download("datasets/mydataset")
self.storage.open()
```

## Logging

`phd_flow` uses [loguru](https://github.com/Delgan/loguru). You can import
a preconfigured logger using `from phd_flow import logger`. See
[loguru's documentation](https://loguru.readthedocs.io/en/stable/index.html)
for more details.

# Integration with other loggers

## wandb

TODO

## mlflow

TODO
