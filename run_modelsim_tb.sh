#!/bin/sh
# ModelSim/Questa alternative. Treat missing PASS and any FAIL as error.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
for TOOL in vlib vlog vsim; do
    command -v "$TOOL" >/dev/null 2>&1 || {
        echo "ERROR: ModelSim/Questa $TOOL not installed" >&2
        exit 127
    }
done
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
cd "$ROOT"
vlib "$TMP/work"
for TEST in xw_job_dim_cfg xw_ddr_range_rx xw_scale_group_cache xw_fp32_scale_b2; do
    echo "Running ModelSim $TEST"
    vlog -work "$TMP/work" "rtl/$TEST.v" "tb/tb_$TEST.v"
    if ! vsim -c -lib "$TMP/work" "tb_$TEST" -do 'run -all; quit -f' \
          > "$TMP/$TEST.log" 2>&1; then
        cat "$TMP/$TEST.log"
        echo "FAIL: ModelSim simulation command failed for $TEST" >&2
        exit 1
    fi
    cat "$TMP/$TEST.log"
    if grep -E '(^|[[:space:]])FAIL([[:space:]:]|$)' "$TMP/$TEST.log" >/dev/null; then
        echo "FAIL: ModelSim $TEST logged a failing test" >&2
        exit 1
    fi
    if [ "$(grep -Ec "PASS tb_$TEST([[:space:]]|$)" "$TMP/$TEST.log" || true)" -ne 1 ]; then
        echo "FAIL: ModelSim $TEST missing or duplicate PASS marker" >&2
        exit 1
    fi
done
# Negative elaboration cases must fail specifically in the parameter guard.
for BAD in job_params cache_params; do
    if [ "$BAD" = "job_params" ]; then RTL=xw_job_dim_cfg; else RTL=xw_scale_group_cache; fi
    BAD_LOG="$TMP/bad_$BAD.log"
    if vlog -work "$TMP/work" "rtl/$RTL.v" "tb/negative/tb_xw_invalid_$BAD.v" \
        > "$BAD_LOG" 2>&1; then
        if vsim -c -lib "$TMP/work" "tb_xw_invalid_$BAD" \
                -do 'run -all; quit -f' >> "$BAD_LOG" 2>&1; then
            echo "FAIL: invalid $BAD parameters unexpectedly elaborated" >&2
            exit 1
        fi
    fi
    if ! grep -F 'XW_INVALID_' "$BAD_LOG" >/dev/null; then
        cat "$BAD_LOG"
        echo "FAIL: invalid $BAD failed for an unexpected reason" >&2
        exit 1
    fi
    echo "PASS invalid parameter elaboration rejected: $BAD"
done
echo 'PASS Stage-1 four-module ModelSim regression and 2 negative elaborations'
