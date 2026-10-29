// These tops must fail elaboration at the named parameter guard.
module tb_xw_invalid_parser_params;
    xw_axis_bfp18_input #(.MAX_K(0)) dut ();
endmodule
module tb_xw_invalid_activation_params;
    xw_activation_buffer #(.MAX_K(65536)) dut ();
endmodule
module tb_xw_invalid_weight_params;
    xw_weight_row_buffer #(.MAX_K(0)) dut ();
endmodule
module tb_xw_invalid_burst_unspecified;
    xw_ddr_addr_gen dut ();
endmodule
module tb_xw_invalid_burst_large;
    xw_ddr_addr_gen #(.DDR_MAX_BURST_BEATS(65536)) dut ();
endmodule
module tb_xw_invalid_address_max;
    xw_ddr_addr_gen #(.MAX_N(0), .DDR_MAX_BURST_BEATS(1)) dut ();
endmodule
