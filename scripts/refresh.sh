#!/usr/bin/env bash
# Rebuild the report from live GitHub + local session data. See README.md.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONIOENCODING=utf-8
PY=$(command -v python3 || command -v python)
"$PY" scripts/collect.py "$@"
"$PY" scripts/sessions.py
"$PY" scripts/aggregate.py
"$PY" scripts/build.py
"$PY" scripts/og.py || echo "og.py failed: dist/index.html is built, only the social card is missing" >&2
