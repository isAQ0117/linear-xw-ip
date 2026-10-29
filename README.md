# Linear xW / B3-B FP32-Scale Cycle Model — V0.2

**Scale profile locked for this revision:** raw IEEE-754 **FP32**, not BF16.
Input BFP18 mantissa/exponent and FP8 E4M3FN weights remain unchanged.
FP32 `scale_fp32_bits` is the exact stored uint32 representation.

This directory contains an executable **architectural cycle-stepped Python model**
and the **first four Verilog-2001 RTL submodules**. It does **not** yet contain a
complete Linear RTL engine, or claim that a ModelSim/Vivado simulation has passed.

## Quick start

No third-party Python dependency is needed.

```bash
python cycle_model.py --out demo_results
python test_cycle.py
python test_fp32.py
```

DDR stalls/latency, AXI gaps and output stalls:
```bash
python cycle_model.py --out gap_results --ddr-latency 5 --ddr-gap 2 \
  --ddr-ready-period 3 --input-gap 1 --output-stall-period 4
```

External prequantized matrices (the future safetensors parser will generate this JSON):
```bash
python cycle_model.py --case my_case.json --out real_results
```

## Input JSON

```json
{
  "job": {
    "job_id": 42, "m": 1, "n": 2, "k": 3,
    "static_dim_mode": 1, "n_dim": 2, "k_dim": 3,
    "weight_base_addr": 0, "axis_width_bits": 512
  },
  "activation": {"mantissa": [[1,2,3]], "exponents": [[0]]},
  "weight": {
    "fp8_bits": [[56,56,56],[56,56,56]],
    "scale_fp32_bits": [[1065353216]]
  }
}
```

- FP8 values are raw uint8 E4M3FN encodings (56/0x38 = 1.0).
- `scale_fp32_bits` are raw **uint32 FP32** encodings (1065353216 / 0x3f800000 = 1.0),
  shaped `[ceil(N/128)][ceil(K/128)]`. Hex strings such as `"0x3f800000"`
  are also accepted for scales.
- Activation is **already BFP18**: signed18 `[M,K]` mantissa, signed8
  exponent `[M,ceil(K/128)]`.
- An optional `"reference":{"float_xw":[[...],...]}` may supply a genuine
  original float-model output to add total quantization/error metrics.
- The `.safetensors` reader is intentionally **not included** yet.
  Its future responsibility is to export correct raw FP8 and FP32 bit patterns,
  preserve the original quantization block order, and supply an independent
  float xW baseline.

## FP32 numeric contract

FP32 Scale must be finite, positive and nonzero. Normal and subnormal FP32 are
decoded exactly, without a Python `float` in the arithmetic path.

| Stage | Format |
|---|---|
| X input | 18-bit signed mantissa, 8-bit signed exponent per 128 K |
| W input | FP8 E4M3FN, decoded as signed Q9 integer |
| Scale | IEEE-754 FP32, 32-bit unmodified raw bit pattern |
| B1 | signed48 raw dot product of <=128 elements |
| B2 | raw48 × 24-bit positive FP32 significand = signed72 full term |
| B2 term exponent | signed12; `E_A - 9 + E_SCALE` |
| A2 | ordered K block accumulation into signed48 + signed16 |
| Output | signed18 BFP group-128 mantissas + signed8 group exponent |

For a normal FP32, `scale = (2^23+frac) * 2^(biased_exp-150)`.
For a subnormal, `scale = frac * 2^(-149)`.

**Important:** A2 receives the FULL signed72 Term with no narrowing to 56 bits.
A2 performs RNE after every K block, preserving the intended 48-bit state.
This is an explicitly **new B3-B-FP32 profile**. The earlier BF16/56-bit
Golden vectors are NOT a bit-exact sign-off reference for this FP32 profile.
The new model checks two paths: an independently scheduled ordered calculation
and an exact rational, no-intermediate-rounding xW calculation.

## DDR layout V3

- `weight`: FP8 `[N,K]` output-channel-major, K contiguous; each row padded
  to a whole 64-byte DDR word.
- `scale`: each **N-group of up to 128 output channels** gets its own
  independently 64-byte-aligned region with `ceil(K/128)` FP32 values, little
  endian, 16 FP32 values per 512-bit DDR word.
- `weight_words_per_row = ceil(K/64)`.
- `scale_words_per_group = ceil(K/2048)`.
- `ddr_rd_addra`/`ddr_rd_addrb` denote an **inclusive range**,
  one 512-bit beat per logical address increment of **8**.
- The DDR read return has no `ready`; model assumes the receiver is provisioned
  to accept all beats. First beat can coincide with accepted request.
- One outstanding range only.

Access order: receive input BFP18 → for each output N-group, prefetch all FP32
Scale → for each output channel load full Weight Row → for each Batch Row process
K Blocks B1→B2→A2 → requantize completed N-group → ultimately output row-major
AXI BFP18 V2. Weight is read once per output channel and reused across Batch Rows.

## Output files

- `cycle_trace.jsonl`: cycle-indexed event trace
- `ddr_image.bin`, `ddr_manifest.json`: exactly packed DDR image, layout V3
- `input_axis_v2.jsonl`, `output_axis_v2.jsonl`: BFP18 512-bit AXIS V2 beats
- `output_numeric.json`: final mantissas and exponent arrays
- `element_errors.csv`: each output versus exact quantized-input xW; optional
  original floating baseline when supplied
- `metrics.json`: Golden pass, latency, DDR requests, total errors

Printed metrics are **not actual RTL latency predictions**. The B1/B2/A2
latency values are user-chosen architectural assumptions and the model
does not simulate B1's individual multiplier lanes or exact FIFO/RAM timing.
Python does not provide 4-state X/Z simulation. Only a real Verilog
simulator running the real RTL can verify those effects.

## RTL started

See `rtl/RTL_DESIGN_STATUS.md` for the implementation boundaries and
`tb/` for Verilog-2001 self-checking testbenches.

If an Icarus Verilog executable is available, run `sh run_rtl_tb.sh`.
Alternatively compile the `.v` files in ModelSim/Vivado. Neither HDL simulator
nor synthesizer is installed in this environment, so **RTL tests supplied
here have not been executed**.

## Environment

The target is Vivado 2023.2 and older ModelSim as possible; RTL deliberately
uses traditional Verilog-2001 without SystemVerilog `logic`, `always_ff`,
interfaces, packages, structures, or `$clog2`.

## Stage 2+3 storage baseline

The current implementation and measured evidence are indexed in
[docs/stage23/DELIVERY_REPORT.md](docs/stage23/DELIVERY_REPORT.md).
This section describes the M=1 input/DDR storage baseline. The Stage4 computing core is now added below; Stage5–8 remain pending.
The historical text above describes V0.2 and is not current signoff status.

```sh
make py-test          # 43 software tests, including Stage2/3 boundary matrices
make rtl-test         # existing four-module Stage1 regression
make stage23-test     # actual Icarus Verilog-2001 PRE/NBA lockstep + integration
make synthesis-check # optional Yosys generic structure/clocked memory checks
```

Dependencies: Python 3 standard library; `iverilog` and `vvp` (tested 12.0);
optional `yosys` (tested 0.33). All commands run from the repository root.
`sim_build/stage23/` is reproducibly generated and ignored by Git. Actual logs,
vector hashes, baseline hashes and reports are under `docs/stage23/`.
`DDR_MAX_BURST_BEATS` must be explicitly set for synthesis; test values do not
represent a DDR controller specification. Target Vivado 2023.2, FPGA mapping,
timing closure, and external transaction cleanup guarantees remain unverified.

## Stage 4计算核心

已实现B1/B2 Pipe/A2及局部Controller，完整复审入口见[REVIEW_STAGE4.md](REVIEW_STAGE4.md)。Stage4数值/真实Icarus/周期/通用结构检查通过，Vivado与目标时序仍Pending。执行`make stage4-test`或`make all-tests`，不要将局部result当作完整Linear Job输出。
