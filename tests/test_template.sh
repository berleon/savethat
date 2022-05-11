#! /usr/bin/env bash

echo "Current working dir:"
pwd
echo ""

savethat_repo="$1"

echo "savethat project:"
$savethat_repo
echo ""

# Initialize a git repository
git init
git add .
git commit -m "Initial commit"

python -m venv venv


source venv/bin/activate
pip install -U pip wheel setuptools cython
pip install $savethat_repo
pip install poetry
poetry install

# list all available nodes
python -m fit_ols nodes

# execute the FitOLS node
python -m test_template run test_template.fit_ols.FitOLS \
    --dataset california \
     --target MedHouseVal
