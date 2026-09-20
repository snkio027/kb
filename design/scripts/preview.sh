#!/bin/sh
# Convenience entry only; every write/compile still goes through pub.py.
set -eu
preview_script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
preview_python=${PDF_PYTHON:-python3}
exec "$preview_python" -B "$preview_script_dir/pub.py" preview "$@"
