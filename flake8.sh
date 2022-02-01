#! /usr/bin/env bash
#
# this script runs flake8 on all clean files.

set -e
echo "Executing flake8..."

source ./scripts/utilities.sh

flake8 \
    --count \
    --show-source \
    --statistics \
    ./test/ \
    ./setup.py \
    "./$MODULE_NAME/" \
    || fail

echo -e "${Green}FLAKE8 PASSED$Color_Off"
