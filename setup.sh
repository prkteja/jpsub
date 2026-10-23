#!/bin/bash
# Development setup: Python environment, then the models and dictionary. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"

[ -d .venv ] || uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m jpsub --setup "$@"
echo "Ready. Start with ./run.sh --overlay"
