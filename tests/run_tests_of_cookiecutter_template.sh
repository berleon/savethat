#! /usr/bin/env bash

# enable trace
set -x
# early exit on error
set -e

echo "Current working dir:"
pwd
echo ""

savethat_repo="$1"

echo "savethat project:"
echo "$savethat_repo"
echo ""

# Needs to be converted to a relative path.
# See: https://github.com/python-poetry/poetry/issues/1692
savethat_repo_rel=$(realpath --relative-to . $savethat_repo)


# Initialize a git repository
git init
git add .
git commit -m "Initial commit"

python -m venv venv


source venv/bin/activate
pip install -U pip wheel setuptools cython
pip install poetry
poetry install

git add .
git commit -m "Add poetry.lock"


poetry add $savethat_repo_rel
poetry show savethat

export COVERAGE_PROCESS_START="$savethat_repo/pyproject.toml"

# list all available nodes
python -m test_template nodes

# execute the FitOLS node
python -m test_template run test_template.fit_ols.FitOLS \
    --dataset california_housing \
     --target MedHouseVal


# run the tests & build docs
make test
mkdocs build
