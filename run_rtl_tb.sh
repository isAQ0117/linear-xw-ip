#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
command -v iverilog >/dev/null 2>&1 || {
    echo "ERROR: Icarus Verilog not installed; use ModelSim/vlog or Vivado xsim." >&2
    exit 127
}
for TEST in xw_fp32_scale_b2 xw_ddr_range_rx xw_scale_group_cache; do
    echo "Running $TEST"
    iverilog -g2001 -s "tb_$TEST" -o "$ROOT/tb/$TEST.out" \
        "$ROOT/rtl/$TEST.v" "$ROOT/tb/tb_$TEST.v"
    vvp "$ROOT/tb/$TEST.out"
done
