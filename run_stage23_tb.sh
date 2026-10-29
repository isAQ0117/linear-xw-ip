#!/bin/sh
# Real HDL only passes when every PRE/NBA record and every PASS check succeeds.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"
python3 tools/gen_stage23_tb.py --check
python3 tools/run_stage23.py
