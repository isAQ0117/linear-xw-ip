`timescale 1ns/1ps
// Stage-1, pure Verilog-2001 dimension configuration contract checks.
module tb_xw_job_dim_cfg;
    reg clk;
    reg rst_n;
    reg job_accept;
    reg [15:0] job_n;
    reg [15:0] job_k;

    wire static_valid, static_error;
    wire [15:0] static_n, static_k;
    wire [9:0] static_groups, static_blocks;
    wire [10:0] static_weight_words;
    wire [5:0] static_scale_words;

    wire dynamic_valid, dynamic_error;
    wire [15:0] dynamic_n, dynamic_k;
    wire [9:0] dynamic_groups, dynamic_blocks;
    wire [10:0] dynamic_weight_words;
    wire [5:0] dynamic_scale_words;

    xw_job_dim_cfg #(
        .STATIC_DIM_MODE(1), .N_DIM(129), .K_DIM(2049),
        .MAX_N(65535), .MAX_K(65535)
    ) u_static (
        .clk(clk), .rst_n(rst_n), .job_accept(job_accept),
        .job_n(job_n), .job_k(job_k),
        .cfg_valid(static_valid), .cfg_error(static_error),
        .active_n(static_n), .active_k(static_k),
        .n_groups(static_groups), .k_blocks(static_blocks),
        .weight_words_per_row(static_weight_words),
        .scale_words_per_group(static_scale_words)
    );

    xw_job_dim_cfg #(
        .STATIC_DIM_MODE(0), .N_DIM(1), .K_DIM(1),
        .MAX_N(65535), .MAX_K(65535)
    ) u_dynamic (
        .clk(clk), .rst_n(rst_n), .job_accept(job_accept),
        .job_n(job_n), .job_k(job_k),
        .cfg_valid(dynamic_valid), .cfg_error(dynamic_error),
        .active_n(dynamic_n), .active_k(dynamic_k),
        .n_groups(dynamic_groups), .k_blocks(dynamic_blocks),
        .weight_words_per_row(dynamic_weight_words),
        .scale_words_per_group(dynamic_scale_words)
    );

    initial clk = 0;
    always #5 clk = ~clk;
    initial begin
        #20000;
        $display("FAIL tb_xw_job_dim_cfg TIMEOUT");
        $finish;
    end

    initial begin
        rst_n = 0; job_accept = 0; job_n = 0; job_k = 0;
        repeat (2) @(negedge clk);
        rst_n = 1;
        @(negedge clk);
        job_accept = 1;
        job_n = 16'd0; job_k = 16'd0;
        @(posedge clk); #1;
        if (static_valid !== 1'b1 || static_error !== 1'b0 ||
            static_n !== 16'd129 || static_k !== 16'd2049 ||
            static_groups !== 10'd2 || static_blocks !== 10'd17 ||
            static_weight_words !== 11'd33 || static_scale_words !== 6'd2 ||
            dynamic_valid !== 1'b1 || dynamic_error !== 1'b1) begin
            $display("FAIL static ignored physical N/K or dynamic zero rejection");
            $finish;
        end
        @(negedge clk); job_accept = 0;
        @(posedge clk); #1;
        if (static_valid !== 1'b0 || dynamic_valid !== 1'b0 ||
            dynamic_error !== 1'b1) begin
            $display("FAIL cfg_valid pulse or cfg_error holding");
            $finish;
        end
        @(negedge clk);
        job_accept = 1; job_n = 16'd65535; job_k = 16'd65535;
        @(posedge clk); #1;
        if (dynamic_error !== 1'b0 || dynamic_n !== 16'd65535 ||
            dynamic_k !== 16'd65535 || dynamic_groups !== 10'd512 ||
            dynamic_blocks !== 10'd512 || dynamic_weight_words !== 11'd1024 ||
            dynamic_scale_words !== 6'd32) begin
            $display("FAIL dynamic maximum dimensions or count width");
            $finish;
        end
        @(negedge clk); job_accept = 0; rst_n = 0;
        #1;
        if (static_valid !== 1'b0 || static_n !== 16'd0 ||
            dynamic_k !== 16'd0 || dynamic_error !== 1'b0) begin
            $display("FAIL asynchronous reset");
            $finish;
        end
        $display("PASS tb_xw_job_dim_cfg");
        $finish;
    end
endmodule
