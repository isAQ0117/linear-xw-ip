#!/bin/sh
# Actual HDL only; missing tools, FAIL, missing/duplicate PASS all fail closed.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"
python3 tools/gen_stage4_tb.py --check
python3 -m unittest -v test_stage4_numeric
python3 tools/run_stage4.py
python3 tools/run_stage4_review.py
python3 tools/check_stage4_mutations.py
python3 tools/report_stage4_performance.py
