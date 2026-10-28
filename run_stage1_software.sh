#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"
python3 tools/gen_b2_vectors.py --check
python3 -m unittest -v test_cycle test_fp32 test_stage1_contract
