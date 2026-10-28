// Verilog-2001. FP32 scale decode and exact 48x24 unsigned-significand multiplication.
// New B3-B-FP32 numerical profile: no BF16 downcast, no 56-bit term truncation.
// For normal FP32: scale = {1, fraction[22:0]} * 2**(E-150).
// For subnormal: scale = fraction[22:0] * 2**(-149).
module xw_fp32_scale_b2 (
    /*
     * =========================================================
     * B1 原始点积与 Activation 指数
     * =========================================================
     */
    input  wire signed [47:0]   b1_raw,
    input  wire signed [7:0]    act_exp,

    /*
     * =========================================================
     * FP32 Scale 原始位模式
     * =========================================================
     */
    input  wire [31:0]          scale_bits,

    /*
     * =========================================================
     * B2 Term 输出
     * =========================================================
     */
    output wire signed [71:0]   term_mant,
    output wire signed [11:0]   term_exp,
    output wire                 scale_valid
);

    /*
     * =========================================================
     * FP32 原始字段解码
     * =========================================================
     */
    wire [7:0]  exp_field;
    wire [22:0] frac_field;

    /*
     * =========================================================
     * Scale 有效尾数与指数转换
     * =========================================================
     */
    wire [23:0] significand;
    wire signed [24:0] positive_sig;
    wire signed [11:0] scale_power;
    wire signed [11:0] act_exp_wide;

    /*
     * 拆出 Scale 指数和小数位，检查正数、有限和非零。
     */
    assign exp_field = scale_bits[30:23];
    assign frac_field = scale_bits[22:0];
    assign scale_valid = !scale_bits[31] &&
                         (exp_field != 8'hff) &&
                         ((exp_field != 8'h00) || (frac_field != 23'd0));

    /*
     * 根据正规化或非正规化 FP32 生成 24-bit 尾数和二进制指数。
     */
    assign significand = (exp_field == 8'd0) ?
                         {1'b0, frac_field} : {1'b1, frac_field};
    // 25-bit signed, always positive, INCLUDING for significand[23]==1.
    assign positive_sig = $signed({1'b0, significand});
    assign scale_power = (exp_field == 8'd0) ?
                         -12'sd149 : $signed({4'b0000, exp_field}) - 12'sd150;
    assign act_exp_wide = {{4{act_exp[7]}}, act_exp};

    /*
     * B2 数值运算：保留 signed72 完整乘积和 signed12 指数。
     */
    // Full signed72 product. B1_raw is signed48; scale significand is positive24.
    assign term_mant = scale_valid ? (b1_raw * positive_sig) : 72'sd0;
    // B1 Q9 implies -9 shift in physical scale exponent.
    assign term_exp = scale_valid ? (act_exp_wide - 12'sd9 + scale_power)
                                  : 12'sd0;
endmodule
