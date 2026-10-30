#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 tools/run_stage67.py --stage 6
python3 tools/run_stage67.py --stage 7
python3 tools/run_stage67.py --stage fault
python3 tools/run_stage67.py --stage extended
python3 tools/run_stage67.py --stage retry
python3 tools/review_stage67.py
python3 tools/report_stage67.py
python3 tools/audit_stage67.py
