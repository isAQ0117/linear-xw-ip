# Vivado 2023.2 exploratory out-of-context implementation.
# Usage: vivado -mode batch -source tools/vivado_stage4.tcl -tclargs <part> [period_ns]
# A real part is REQUIRED. This file does not claim that Vivado has been run.
if {$argc < 1} {
    error "Specify the actual target FPGA part; no ungrounded part default is provided."
}
set target_part [lindex $argv 0]
set period_ns 10.0
if {$argc > 1} { set period_ns [lindex $argv 1] }
set repo_root [file normalize [file join [file dirname [info script]] ..]]
set output_dir [file join $repo_root sim_build vivado_stage4]
file mkdir $output_dir
foreach name {xw_fp32_scale_b2 xw_b1_dot128 xw_b2_fp32_pipe xw_a2_accum48 xw_b3b_compute_ctrl} {
    read_verilog [file join $repo_root rtl ${name}.v]
}
synth_design -top xw_b3b_compute_ctrl -part $target_part -mode out_of_context
create_clock -name compute_clk -period $period_ns [get_ports clk]
report_utilization -file [file join $output_dir post_synth_utilization.rpt]
report_timing_summary -file [file join $output_dir post_synth_timing.rpt]
opt_design
place_design
phys_opt_design
route_design
report_utilization -file [file join $output_dir routed_utilization.rpt]
report_timing_summary -report_unconstrained -file [file join $output_dir routed_timing.rpt]
report_drc -file [file join $output_dir drc.rpt]
report_methodology -file [file join $output_dir methodology.rpt]
write_checkpoint -force [file join $output_dir stage4_routed.dcp]
# Integrator must supply external input/output delays, reset-domain review and
# system constraints before using these reports as signoff evidence.
