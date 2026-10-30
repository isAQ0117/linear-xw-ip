# Real Vivado entry point. Supply audited FPGA part, period, platform burst.
# vivado -mode batch -source tools/vivado_stage67.tcl -tclargs PART PERIOD_NS BURST
if {$argc != 3} { error "Require FPGA_PART CLOCK_PERIOD_NS PLATFORM_DDR_BURST" }
lassign $argv part period burst
if {$burst < 1 || $burst > 65535} { error "Invalid audited burst" }
create_project -in_memory -part $part
set_property verilog_define [list XW_PLATFORM_DDR_BURST=$burst] [current_fileset]
read_verilog [glob rtl/*.v]
synth_design -top linear_xw_ip -part $part
create_clock -name core_clk -period $period [get_ports clk]
report_utilization -file docs/stage67/vivado_utilization.rpt
report_timing_summary -file docs/stage67/vivado_post_synth_timing.rpt
report_drc -file docs/stage67/vivado_drc.rpt
write_checkpoint -force sim_build/stage67/vivado_synth.dcp
# IO delays and board/platform constraints must be added before timing sign-off.
