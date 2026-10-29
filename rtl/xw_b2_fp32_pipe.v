`timescale 1ns / 1ps

/* 两级弹性包装；原B2数学表达式与精度完全复用。 */
module xw_b2_fp32_pipe (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                abort,
    input  wire                in_valid,
    output wire                in_ready,
    input  wire signed [47:0]   in_raw,
    input  wire signed [7:0]    in_exp,
    input  wire [31:0]          in_scale,
    input  wire [15:0]          in_block,
    output wire                out_valid,
    input  wire                out_ready,
    output reg signed [71:0]   out_mant,
    output reg signed [11:0]   out_exp,
    output reg [15:0]          out_block,
    output reg [7:0]           out_error
);

    /* 输入锁存、输出槽及精确组合B2。 */
    reg v0;
    reg v1;
    reg signed [47:0] raw0;
    reg signed [7:0] exp0;
    reg [31:0] scale0;
    reg [15:0] block0;
    wire ready1;
    wire signed [71:0] term_mant;
    wire signed [11:0] term_exp;
    wire scale_valid;

    assign ready1 = !v1 || out_ready;
    assign in_ready = rst_n && !abort && (!v0 || ready1);
    assign out_valid = rst_n && !abort && v1;

    xw_fp32_scale_b2 exact_b2 (
        .b1_raw(raw0),
        .act_exp(exp0),
        .scale_bits(scale0),
        .term_mant(term_mant),
        .term_exp(term_exp),
        .scale_valid(scale_valid)
    );

    /* 只在后级可推进时覆盖数据；stall期间全部payload和错误码保持。 */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            v0 <= 0;
            v1 <= 0;
            raw0 <= 0;
            exp0 <= 0;
            scale0 <= 0;
            block0 <= 0;
            out_mant <= 0;
            out_exp <= 0;
            out_block <= 0;
            out_error <= 0;
        end else if (abort) begin
            v0 <= 0;
            v1 <= 0;
        end else begin
            if (ready1) begin
                v1 <= v0;
                if (v0) begin
                    out_mant <= term_mant;
                    out_exp <= term_exp;
                    out_block <= block0;
                    out_error <= scale_valid ? 8'd0 : 8'h30;
                end
            end
            if (in_ready) begin
                v0 <= in_valid;
                if (in_valid) begin
                    raw0 <= in_raw;
                    exp0 <= in_exp;
                    scale0 <= in_scale;
                    block0 <= in_block;
                end
            end
        end
    end
endmodule
