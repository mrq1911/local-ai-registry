#!/usr/bin/env bash
set -euo pipefail

bench_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 -c 'import sys; assert sys.version_info >= (3, 12), "python 3.12 or newer is required"'
mkdir -p "$bench_dir/.cache/tmp"
export TMPDIR="$bench_dir/.cache/tmp"
export PIP_CACHE_DIR="$bench_dir/.cache/pip"
python3 -m venv "$bench_dir/.venv"
"$bench_dir/.venv/bin/python" -m pip install -r "$bench_dir/requirements.txt"
"$bench_dir/.venv/bin/python" -m pip check
