# Stage-1 pure Verilog-2001: ModelSim / Icarus regression

The Stage-1 baseline contains **four modules, four self-checking testbenches, and two negative-elaboration testbenches**:

- `tb_xw_job_dim_cfg.v` — static/dynamic N/K, maximum widths, reset.
- `tb_xw_ddr_range_rx.v` — same-edge first beat, gaps, handoff guard,
  fatal sticky `0x20/0x21`, reset gating, DDR Ready stall.
- `tb_xw_scale_group_cache.v` — FP32 words, group reload, extra Beat,
  write/config collision, early read, sticky `0x23/0x40`.
- `tb_xw_fp32_scale_b2.v` — **512 deterministic bit-exact vectors**,
  from `tb/vectors/b2_fp32_vectors.mem` (normal/subnormal/invalid/extrema).

The two files under `tb/negative/` deliberately instantiate illegal static
parameters; the runners require elaboration to fail with the named guard.

Start from the full project root (the directory containing `rtl/` and `tb/`):

```sh
./run_modelsim_tb.sh
```

Or, for Icarus:

```sh
./run_rtl_tb.sh
```

The runner **fails on compile errors, simulation errors, any `FAIL` text,
missing PASS, or duplicate PASS**.  Testbenches remain pure Verilog-2001
and use `$finish`, rather than SystemVerilog `$fatal` assertions.  A PASS
printed by one TB does not substitute for the full regression.

To reproduce the B2 data before simulation:

```sh
python3 tools/gen_b2_vectors.py --check
```

To run the accompanying software contract model and the preserved V0.2 suite:

```sh
./run_stage1_software.sh
```

**Important:** Running Python tests or these static checks is NOT equivalent
to HDL compilation or simulation.  No tool status should be recorded as PASS
until the HDL scripts actually complete on a machine with a supported tool.
