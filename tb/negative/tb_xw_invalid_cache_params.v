`timescale 1ns/1ps
// EXPECTED ELABORATION FAILURE: one word is too small for MAX_K=2049.
module tb_xw_invalid_cache_params;
    xw_scale_group_cache #(
        .MAX_K(2049), .MAX_SCALE_WORDS(1)
    ) u_invalid ();
endmodule
