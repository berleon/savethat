#! /usr/bin/env bash
#
# this script runs flake8 on all clean files.

set -e
echo "Executing mypy..."

source scripts/utilities.sh

python -m mypy \
    "${MODULE_NAME}/" \
    test/ \
    setup.py  \
    "$@"
