`timescale 1ns/1ps
// EXPECTED ELABORATION FAILURE: invalid static dimensions exceed MAX_N.
module tb_xw_invalid_job_params;
    xw_job_dim_cfg #(
        .STATIC_DIM_MODE(1), .N_DIM(129), .K_DIM(1),
        .MAX_N(128), .MAX_K(1)
    ) u_invalid ();
endmodule
