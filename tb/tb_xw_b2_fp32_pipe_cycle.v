`timescale 1ns / 1ps
/* 自动生成；完整比较沿前组合输出及沿后NBA，期望另经数学Golden检查。 */
module tb_xw_b2_fp32_pipe_cycle;
    /* 驱动与观测端口。 */
    reg  [0:0] clk;
    reg  [0:0] rst_n;
    reg  [0:0] abort;
    reg  [0:0] in_valid;
    wire [0:0] in_ready;
    reg  [47:0] in_raw;
    reg  [7:0] in_exp;
    reg  [31:0] in_scale;
    reg  [15:0] in_block;
    wire [0:0] out_valid;
    reg  [0:0] out_ready;
    wire [71:0] out_mant;
    wire [11:0] out_exp;
    wire [15:0] out_block;
    wire [7:0] out_error;
    reg [107:0] stimulus;
    reg [109:0] expected_pre;
    reg [109:0] expected_post;
    reg [4095:0] vector_path;
    integer fd;
    integer scanned;
    integer cycles;

    xw_b2_fp32_pipe dut (
        .clk(clk),
        .rst_n(rst_n),
        .abort(abort),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_raw(in_raw),
        .in_exp(in_exp),
        .in_scale(in_scale),
        .in_block(in_block),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_mant(out_mant),
        .out_exp(out_exp),
        .out_block(out_block),
        .out_error(out_error)
    );

    /* 统一时钟。 */
    always #5 clk = ~clk;

    /* 仿真超时必须失败，禁止用挂起冒充错误处理。 */
    initial begin
        #100000000;
        $display("FAIL timeout");
        $finish;
    end

    /* 在下降沿驱动，稳定后比较PRE，上升沿后比较NBA。 */
    initial begin
        clk = 0;
        rst_n = 1;
        cycles = 0;
        if (!$value$plusargs("VECTORS=%s", vector_path)) begin
            $display("FAIL missing VECTORS"); $finish;
        end
        fd = $fopen(vector_path, "r");
        if (!fd) begin $display("FAIL vectors open"); $finish; end
        while (!$feof(fd)) begin
            scanned = $fscanf(fd, "%h %h %h\n", stimulus, expected_pre, expected_post);
            if (scanned != 3) begin $display("FAIL malformed vectors"); $finish; end
            @(negedge clk);
            {rst_n, abort, in_valid, in_raw, in_exp, in_scale, in_block, out_ready} = stimulus;
            #1;
            if ({in_ready, out_valid, out_mant, out_exp, out_block, out_error} !== expected_pre) begin
                $display("FAIL xw_b2_fp32_pipe PRE cycle=%0d actual=%h expected=%h", cycles, {in_ready, out_valid, out_mant, out_exp, out_block, out_error}, expected_pre);
                $finish;
            end
            @(posedge clk);
            #1;
            if ({in_ready, out_valid, out_mant, out_exp, out_block, out_error} !== expected_post) begin
                $display("FAIL xw_b2_fp32_pipe NBA cycle=%0d actual=%h expected=%h", cycles, {in_ready, out_valid, out_mant, out_exp, out_block, out_error}, expected_post);
                $finish;
            end
            cycles = cycles + 1;
        end
        $fclose(fd);
        if (cycles < 5) begin $display("FAIL empty vectors"); $finish; end
        $display("PASS tb_xw_b2_fp32_pipe_cycle cycles=%0d", cycles);
        $finish;
    end
endmodule
