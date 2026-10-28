# Pure Verilog-2001 ModelSim instructions

Run each testbench independently from the project root:

```
vlog rtl/xw_fp32_scale_b2.v tb/tb_xw_fp32_scale_b2.v
vsim -c tb_xw_fp32_scale_b2 -do "run -all; quit -f"

vlog rtl/xw_ddr_range_rx.v tb/tb_xw_ddr_range_rx.v
vsim -c tb_xw_ddr_range_rx -do "run -all; quit -f"

vlog rtl/xw_scale_group_cache.v tb/tb_xw_scale_group_cache.v
vsim -c tb_xw_scale_group_cache -do "run -all; quit -f"
```

The testbenches use `$display` and `$finish`, rather than SystemVerilog
assertions. Expected passing text is `PASS tb_<module>`.
They have not been run in this environment because there is no HDL simulator.
