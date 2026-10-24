#!/usr/bin/env bash
# Run a FORGE hook script with the first working Python 3.10+.
# python3 comes first (macOS/Linux); on Windows it is often the Microsoft
# Store stub, so each candidate is checked before use.
# Usage: py.sh <script.py>
here="$(cd "$(dirname "$0")" && pwd)"
export PYTHONUTF8=1
check='import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
for py in python3 python "py -3"; do
    if $py -c "$check" >/dev/null 2>&1; then
        exec $py "$here/$1"
    fi
done
echo "FORGE: no Python 3.10+ found (tried python3, python, py -3)" >&2
exit 0
