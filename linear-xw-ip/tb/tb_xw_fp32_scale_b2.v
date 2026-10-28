`timescale 1ns/1ps
// Verilog-2001 direct-combinational B2 checks (no SV).
module tb_xw_fp32_scale_b2;
    reg signed [47:0] raw;
    reg signed [7:0] exp;
    reg [31:0] scale;
    wire signed [71:0] term;
    wire signed [11:0] term_e;
    wire valid;

    xw_fp32_scale_b2 dut (
        .b1_raw(raw), .act_exp(exp), .scale_bits(scale),
        .term_mant(term), .term_exp(term_e), .scale_valid(valid)
    );
    initial begin
        raw = 48'sd100000; exp = -8'sd7; scale = 32'h3f800000;
        #2;
        if (valid !== 1'b1 || term !== 72'sd838860800000 ||
            term_e !== -12'sd39) begin
            $display("FAIL normal FP32 1.0 term=%d exp=%d",term,term_e);
            $finish;
        end
        raw = -48'sd123456; exp = 8'sd5; scale = 32'h3f80624e;
        #2;
        if (valid !== 1'b1 || term !== -72'sd1038730882944 ||
            term_e !== -12'sd27) begin
            $display("FAIL fractional FP32");
            $finish;
        end
        raw = 48'sd7; exp = 8'sd0; scale = 32'h00000001;
        #2;
        if (valid !== 1'b1 || term !== 72'sd7 ||
            term_e !== -12'sd158) begin
            $display("FAIL FP32 subnormal");
            $finish;
        end
        raw = 48'sd7; exp = 8'sd0; scale = 32'hbf800000;
        #2;
        if (valid !== 1'b0 || term !== 72'sd0) begin
            $display("FAIL negative scale rejection");
            $finish;
        end
        $display("PASS tb_xw_fp32_scale_b2");
        $finish;
    end
endmodule
