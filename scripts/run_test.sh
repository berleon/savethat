#! /usr/bin/env bash
#
# this script should pass before committing. It executes flake8 and pytest
# and has a non-zero exit code if one fails.
#
# The script will forward any command line arguments to pytest, e.g.:
#
#   $ ./run_test.sh -k test_blender_rending
#
# will only test the ``test_blender_rending`` function.
#


source ./scripts/utilities.sh

# Early stop the test if there are Python syntax errors or undefined names.
echo "Executing flake sanity checks..."
flake8 "./$MODULE_NAME" \
       ./test  \
       ./setup.py  \
       --select=E9,F63,F7,F82 \
       --show-source \
       --statistics || \
       fail

echo "Executing pytest..."
python -m pytest -v -s test/  \
    -m "not slow" \
    "$@"

pytest_ret=$?

./scripts/mypy.sh
mypy_ret=$?

./scripts/flake8.sh
flake_ret=$?


# if one is non-zero the sum is non-zero
exit_code=$((flake_ret + pytest_ret + mypy_ret))

if [[ "$exit_code" != "0" ]]; then
    echo -e "${Red}SOMETHING FAILED :($Color_Off"
    exit 1
else
    echo -e "${Green}ALL PASSED :)$Color_Off"
fi
