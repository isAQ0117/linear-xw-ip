# Vivado 2023.2 OOC entry; actual FPGA part REQUIRED, no timing claim until run.
# vivado -mode batch -source tools/vivado_stage5.tcl -tclargs <part> <period_ns> [MAX_N]
if {$argc < 2} { error "Specify actual FPGA part and clock period in ns" }
set target_part [lindex $argv 0]
set period_ns [lindex $argv 1]
set max_n 12288
if {$argc > 2} { set max_n [lindex $argv 2] }
if {$max_n < 1 || $max_n > 65535} { error "MAX_N out of range" }
set root [file normalize [file join [file dirname [info script]] ..]]
set out [file join $root sim_build vivado_stage5]
file mkdir $out
foreach name {xw_output_group_buffer xw_bfp18_requant xw_result_buffer xw_stage5_ctrl} {
    read_verilog [file join $root rtl ${name}.v]
}
synth_design -top xw_stage5_ctrl -part $target_part -mode out_of_context -generic MAX_N=$max_n
create_clock -name stage5_clk -period $period_ns [get_ports clk]
report_utilization -hierarchical -file [file join $out post_synth_utilization.rpt]
report_timing_summary -file [file join $out post_synth_timing.rpt]
opt_design
place_design
phys_opt_design
route_design
report_utilization -file [file join $out routed_utilization.rpt]
report_timing_summary -report_unconstrained -file [file join $out routed_timing.rpt]
report_drc -file [file join $out drc.rpt]
write_checkpoint -force [file join $out stage5_routed.dcp]
# System integrator must add external I/O delays and review common reset release.
