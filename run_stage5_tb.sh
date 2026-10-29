#!/bin/sh
# Pure Verilog-2001, fail closed on compiler/run errors, FAIL or missing PASS.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"
python3 tools/run_stage5_all.py
