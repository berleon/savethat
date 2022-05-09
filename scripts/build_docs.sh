#!/bin/bash

set -eu


die () { echo "ERROR: $*" >&2; exit 2; }

for cmd in pdoc; do
    command -v "$cmd" >/dev/null ||
        die "Missing $cmd; \`pip install $cmd\`"
done

BUILDROOT="docs/build"


echo
echo 'Building API reference docs'
echo "Output is saved to: $BUILDROOT"
echo

rm -r "$BUILDROOT" 2>/dev/null || true
mkdir -p "$BUILDROOT"

python ./scripts/run_pdoc.py -d google \
      --output-dir "$BUILDROOT" \
      savethat
