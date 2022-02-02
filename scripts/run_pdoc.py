#! /usr/bin/env python
import re
import sys

import git  # noqa
from pdoc.__main__ import cli

import phd_flow  # noqa

if __name__ == "__main__":
    sys.argv[0] = re.sub(r"(-script\.pyw|\.exe)?$", "", sys.argv[0])
    sys.exit(cli())
