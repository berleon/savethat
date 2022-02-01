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
