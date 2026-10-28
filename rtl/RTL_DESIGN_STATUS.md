# Linear xW RTL — Stage 1 Contract Alignment (FP32 V0.2)

**Fixed route:** `XW-DEV-STD-001 V1.0`, Stage 1 of 9.  
**Frozen behavior:** `XW-CONTRACT-STD-001 V1.0`.  
**Current verification status:** `STAGE1_IMPLEMENTED_HDL_PENDING`, **NOT PASS**.

The four Verilog-2001 modules now include the Stage-1 contract improvements.
They remain standalone submodules, **not** a full connected Linear IP.
No FPGA synthesis, timing closure or actual HDL simulation is claimed.

| RTL | Contract behavior | I/O | HDL execution |
|---|---|---:|---|
| `xw_job_dim_cfg.v` | Static/dynamic N/K and compile-time parameter rejection | 13 | Pending |
| `xw_ddr_range_rx.v` | DDR single outstanding / same-edge first Beat; sticky faults and 1-cycle completion guard | 22 | Pending |
| `xw_scale_group_cache.v` | Group-local FP32 Scale words; sticky faults and safe load/read | 15 | Pending |
| `xw_fp32_scale_b2.v` | Exact signed72 term / signed12 exponent, original arithmetic unchanged | 6 | Pending |

The two new **internal** outputs are `range_error_code[7:0]` and
`cache_error_code[7:0]`.  **No changes to the frozen 35-port TOP ABI.**
The DDR physical interface remains exactly six signals.  Old
transmissions cannot be safely reclaimed without external DDR cleanup.

### Stage-1 tests

- 4 pure Verilog-2001 TBs, including newly added Job Dimension Config TB.
- Reproducible B2 vector file: `tb/vectors/b2_fp32_vectors.mem` (512 lines).
- `stage1_contract_model.py` + `test_stage1_contract.py` provide separate
  Python edge-based reference behavior and error-injection tests.
- `run_rtl_tb.sh` / `run_modelsim_tb.sh` reject any FAIL, missing PASS or
  duplicated PASS; they do not silently accept `$finish` after failure.

Do not proceed to Stage-2 IP implementation as if Stage 1 were verified.
Refer to `docs/stage1/STAGE1_RTL_CONTRACT_ALIGNMENT.md` for requirements,
clock-boundary assumptions and exact verification gaps.

### Future modules — original 9-stage route unchanged

Stage 2: AXIS Input + Activation Buffer; Stage 3: DDR Address Generator and
Weight Row Buffer; Stage 4: B1/B2/A2; Stage 5: Requant and Output Buffer;
Stage 6: AXIS Output and Job Status; Stage 7: Scheduler / TOP integration;
Stage 8: M_TILE and real model weights.
