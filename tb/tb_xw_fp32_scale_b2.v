`timescale 1ns/1ps
// Exact signed72/signed12 B2 vectors: normal/subnormal/invalid/extrema.
// Vector format: {raw48,act_exp8,scale_bits32,term72,term_exp12,valid1}.
module tb_xw_fp32_scale_b2;
    localparam integer VECTOR_COUNT = 512;

    reg  signed [47:0] raw;
    reg  signed  [7:0] exp;
    reg         [31:0] scale;
    wire signed [71:0] term;
    wire signed [11:0] term_e;
    wire               valid;

    reg [172:0] vectors [0:VECTOR_COUNT-1];
    reg signed [71:0] exp_term;
    reg signed [11:0] exp_term_e;
    reg               exp_valid;
    integer i;

    xw_fp32_scale_b2 dut (
        .b1_raw(raw), .act_exp(exp), .scale_bits(scale),
        .term_mant(term), .term_exp(term_e), .scale_valid(valid)
    );

    initial begin
        $readmemh("tb/vectors/b2_fp32_vectors.mem", vectors);
        raw = 0; exp = 0; scale = 0;
        exp_term = 0; exp_term_e = 0; exp_valid = 0;
        for (i = 0; i < VECTOR_COUNT; i = i + 1) begin
            if (^vectors[i] === 1'bx) begin
                $display("FAIL missing or malformed B2 vector index=%0d", i);
                $finish;
            end
            {raw, exp, scale, exp_term, exp_term_e, exp_valid} = vectors[i];
            #2;
            if (valid !== exp_valid || term !== exp_term ||
                term_e !== exp_term_e) begin
                $display("FAIL B2 vector i=%0d raw=%h act=%h scale=%h", 
                         i, raw, exp, scale);
                $display("expected valid=%b term=%h exp=%h", 
                         exp_valid, exp_term, exp_term_e);
                $display("actual   valid=%b term=%h exp=%h", 
                         valid, term, term_e);
                $finish;
            end
        end
        $display("PASS tb_xw_fp32_scale_b2 vectors=%0d", VECTOR_COUNT);
        $finish;
    end
endmodule
