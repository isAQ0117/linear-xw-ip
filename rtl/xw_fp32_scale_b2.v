// Linear xW B2: exact FP32 Scale decode and signed72 term generation.
// Stage 1 contract: XW-CONTRACT-STD-001 V1.0; Verilog-2001, ANSI ports.
// The arithmetic is preserved from the original FP32 V0.2 implementation.
module xw_fp32_scale_b2 (
    input  wire signed [47:0] b1_raw,
    input  wire signed  [7:0] act_exp,
    input  wire        [31:0] scale_bits,
    output wire signed [71:0] term_mant,
    output wire signed [11:0] term_exp,
    output wire               scale_valid
);

    /*
     * =========================================================
     * IEEE-754 FP32 原始位解码（仅正、有限、非零）。
     * =========================================================
     * normal:    S={1,frac} * 2^(biased_exp - 150)
     * subnormal: S=frac     * 2^(-149)
     * No BF16 conversion and no narrowing of signed72 term.
     */
    wire        [7:0] exp_field;
    wire       [22:0] frac_field;
    wire       [23:0] significand;
    wire signed [24:0] positive_sig;
    wire signed [11:0] scale_power;
    wire signed [11:0] act_exp_wide;

    assign exp_field  = scale_bits[30:23];
    assign frac_field = scale_bits[22:0];
    assign scale_valid = !scale_bits[31] &&
                         (exp_field != 8'hff) &&
                         ((exp_field != 8'h00) || (frac_field != 23'd0));

    assign significand = (exp_field == 8'd0) ?
                         {1'b0, frac_field} : {1'b1, frac_field};
    // Sign protection: 24-bit significand must remain a POSITIVE signed25.
    assign positive_sig = $signed({1'b0, significand});
    assign scale_power = (exp_field == 8'd0) ?
                         -12'sd149 : $signed({4'b0000, exp_field}) - 12'sd150;
    assign act_exp_wide = {{4{act_exp[7]}}, act_exp};

    /*
     * =========================================================
     * B2 精确 Term 输出；仅 scale_valid 为 1 时允许 A2 消费。
     * =========================================================
     */
    assign term_mant = scale_valid ? (b1_raw * positive_sig) : 72'sd0;
    assign term_exp  = scale_valid ? (act_exp_wide - 12'sd9 + scale_power)
                                   : 12'sd0;
endmodule
