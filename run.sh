#!/bin/bash
# Run jpsub from the source checkout (same options as the installed binary).
cd "$(dirname "$0")"
exec .venv/bin/python -m jpsub "$@"
