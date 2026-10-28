#!/bin/sh
# Stage-1 regression: fail closed on ANY HDL compile/run error, FAIL log,
# missing PASS marker, or duplicate PASS marker.  Pure Verilog-2001.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
command -v iverilog >/dev/null 2>&1 || {
    echo "ERROR: Icarus Verilog not installed; use ModelSim/vlog or Vivado xsim." >&2
    exit 127
}
command -v vvp >/dev/null 2>&1 || {
    echo "ERROR: vvp not installed." >&2
    exit 127
}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
cd "$ROOT"
for TEST in xw_job_dim_cfg xw_ddr_range_rx xw_scale_group_cache xw_fp32_scale_b2; do
    echo "Running $TEST"
    iverilog -g2001 -Wall -s "tb_$TEST" -o "$TMP/$TEST.out" \
        "rtl/$TEST.v" "tb/tb_$TEST.v"
    if ! vvp "$TMP/$TEST.out" > "$TMP/$TEST.log" 2>&1; then
        cat "$TMP/$TEST.log"
        echo "FAIL: $TEST simulation command failed" >&2
        exit 1
    fi
    cat "$TMP/$TEST.log"
    if grep -E '(^|[[:space:]])FAIL([[:space:]:]|$)' "$TMP/$TEST.log" >/dev/null; then
        echo "FAIL: $TEST logged a failing test" >&2
        exit 1
    fi
    if [ "$(grep -Ec "^PASS tb_$TEST([[:space:]]|$)" "$TMP/$TEST.log" || true)" -ne 1 ]; then
        echo "FAIL: $TEST missing or duplicate PASS marker" >&2
        exit 1
    fi
done
# Deliberate negative-elaboration tests: invalid static parameters MUST fail.
# Checking the error token avoids treating unrelated parser failures as PASS.
for BAD in job_params cache_params; do
    if [ "$BAD" = "job_params" ]; then RTL=xw_job_dim_cfg; else RTL=xw_scale_group_cache; fi
    if iverilog -g2001 -s "tb_xw_invalid_$BAD" -o "$TMP/bad_$BAD.out" \
        "rtl/$RTL.v" "tb/negative/tb_xw_invalid_$BAD.v" \
        > "$TMP/bad_$BAD.log" 2>&1; then
        echo "FAIL: invalid $BAD parameters unexpectedly elaborated" >&2
        exit 1
    fi
    if ! grep -F 'XW_INVALID_' "$TMP/bad_$BAD.log" >/dev/null; then
        cat "$TMP/bad_$BAD.log"
        echo "FAIL: invalid $BAD failure was not the expected guard" >&2
        exit 1
    fi
    echo "PASS invalid parameter elaboration rejected: $BAD"
done
echo 'PASS Stage-1 four-module RTL regression and 2 negative elaborations'
