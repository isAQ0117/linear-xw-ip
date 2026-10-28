# RTL design started — V0.2 FP32 profile

These files are **real Verilog-2001 submodules**, not a complete connected
Linear IP. They were authored after the FP32 Python cycle model and unit tests
were executed. There is no claim of FPGA synthesis or RTL simulation pass.

## Completed source modules

| File | Purpose | Verification status |
|---|---|---|
| `xw_job_dim_cfg.v` | Static parameter vs dynamic Job N/K latch; compute N-group, K-block, weight and FP32-scale DDR word counts | Equations tested in Python; HDL test pending |
| `xw_ddr_range_rx.v` | Legacy FFN six-signal DDR range handshake, one outstanding, same-cycle first return, every valid beat into an unconditional receiver | Verilog TB written; not executed |
| `xw_scale_group_cache.v` | Per-128-output FP32 Scale group in 512-bit words; synchronous indexed read; batch cache invalidation at load_begin | Verilog TB written; not executed |
| `xw_fp32_scale_b2.v` | FP32 normal/subnormal decoder, signed48 × 24-bit multiplier producing signed72 Term and signed12 exponent | Python checked; Verilog TB written; not executed |

DDR physical interface does not change: `ddr_rd_req`, `ddr_rd_addra[28:0]`,
`ddr_rd_addrb[28:0]`, `ddr_rd_rdy`, `ddr_rd_data[511:0]`, `ddr_rd_vld`.
DDR request address calculations remain the responsibility of a dedicated
scheduler / address generator. `xw_ddr_range_rx` accepts fully formed ranges.

In the receiver, every asserted DDR response beat is sampled.
The downstream Weight Buffer / Scale Cache must accept it with **no backpressure**.
The receiver provides `word_valid`, `word_data`, `word_index`, and `word_kind`,
plus an end-of-range pulse and sticky error indication.

## Next construction modules

1. `xw_axis_bfp18_input.v` with physical TUSER V2 and full group decoding.
2. `xw_activation_buffer.v` plus parameterized `xw_weight_row_buffer.v`.
3. `xw_b1_dot128.v` with configurable P_K and B3-B signed48 output.
4. `xw_a2_accum48.v` with exact FP32 signed72 input, signed48/signed16 output,
   ordered updates and explicit RNE (the most critical verification step).
5. `xw_bfp18_requant.v` for output groups of up to 128 elements.
6. `xw_axis_bfp18_output.v` with backpressure-safe payload hold.
7. `xw_linear_scheduler.v` and `linear_xw_ip.v` integrating all submodules,
   `job_valid/job_ready`, `status_valid/status_ready`, AXI/DDR.

All calculations and cache resources are sized from effective K and N,
either compile-time N_DIM/K_DIM or latched job_n/job_k. No 4096 or 12288
hardcoding in the main RTL data path.

## Planned top-level parameters

`STATIC_DIM_MODE=1`, `N_DIM=12288`, `K_DIM=4096`, `MAX_N=12288`,
`MAX_K=12288`, `MAX_M=1`, `MAX_M_TILE=1`, `P_N=1`, `P_K=8`,
`AXIS_DATA_W=512`.

FP32 scale format is fixed for this first profile. DDR returns fixed
512-bit, logical 29-bit address step8 and inclusive end. No new
`SCALE_FORMAT` runtime signal is required.

## Planned top-level signals (35 physical named ports)

- Clock: `clk`,`rst_n` (2)
- Job: `job_valid`,`job_ready`,`job_id[31:0]`,`job_m[15:0]`,
  `job_n[15:0]`,`job_k[15:0]`,`job_m_tile[7:0]`,
  `job_weight_base[28:0]`,`job_scale_base[28:0]` (9)
- Status: `busy`,`status_valid`,`status_ready`,`status_job_id[31:0]`,
  `status_ok`,`status_error_code[7:0]` (6)
- Input AXIS: `s_axis_tdata[AXIS_DATA_W-1:0]`,`s_axis_tvalid`,
  `s_axis_tready`,`s_axis_tkeep[AXIS_DATA_W/8-1:0]`,
  `s_axis_tlast`,`s_axis_tuser[127:0]` (6)
- Output AXIS: same six named `m_axis_*` (6)
- DDR: six physical signals listed above (6)

Total: 2+9+6+6+6+6 = 35. These are ports, not total signal bits.

## Numerical contract to verify at each stage

- B1 RAW is signed48 exact Q9 dot product per K Block.
- B2: `ScaleFP32 > 0, finite`; Term=RAW × positive24, signed72;
  exponent=activation_exp - 9 + scale_binary_power, signed12.
- A2: K Block order is ascending, state signed48+signed16, RNE
  AFTER EACH term; no arbitrary K-block reorder, no narrowing to signed56.
- Output BFP18: 128-element group shares E8; 18-bit signed Mantissas.
- Distinguish internal bit-exact status from comparison against a separately
  computed float-model reference. They measure different correctness claims.

## No HDL simulator available here

The environment's PATH contains no `iverilog`, `verilator`, `vlog`,
`vsim`, `xvlog`, or `xsim`, so it is not possible to claim that these newly
written `.v` modules were actually compiled or wave-tested. Python has been
run and validated. Run the provided Testbenches on the intended installation
before moving to RTL integration. Vivado synthesis has not been attempted.
