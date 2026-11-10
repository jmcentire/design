#!/usr/bin/env bash
# Per-user install. Does not change shared stores, credentials, or network binding.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON=${PYTHON:-python3.12}
"$PYTHON" -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ required"'
"$PYTHON" -m venv .venv
.venv/bin/python -m pip install -r requirements-runtime.lock
.venv/bin/python -m pip install --no-deps -e .
if [[ "${1:-}" == --with-browser ]]; then .venv/bin/python -m playwright install chromium; fi
printf '\nReady: .venv/bin/kinbase-design serve --library /path/to/shared-library-checkout/library\n'
