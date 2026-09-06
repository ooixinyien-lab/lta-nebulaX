#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  printf 'Create the environment first; see README.md.
'
  exit 1
fi
exec .venv/bin/python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
