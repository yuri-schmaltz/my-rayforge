#!/bin/sh

set -e

# Make sure script is started from repo root.
if [ "$0" != 'scripts/generate_uml.sh' ]; then
    echo -e '\033[31m(ERROR)\033[0m: Script called from wrong dir. Please start from the root of the repository'
    exit 1
fi

pyreverse -m y --output png rayforge/ops* rayforge/modifier/ rayforge/models rayforge/render/ \
    && echo Built classes.png and packages.png
