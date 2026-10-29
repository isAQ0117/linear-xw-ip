`timescale 1ns / 1ps
/* 自动生成；完整比较沿前组合输出及沿后NBA，期望另经数学Golden检查。 */
module tb_xw_b1_dot128_cycle;
    /* 驱动与观测端口。 */
    reg  [0:0] clk;
    reg  [0:0] rst_n;
    reg  [0:0] abort;
    reg  [0:0] in_valid;
    wire [0:0] in_ready;
    reg  [143:0] in_x;
    reg  [63:0] in_w;
    reg  [7:0] in_mask;
    reg  [7:0] in_exp;
    reg  [15:0] in_block;
    reg  [3:0] in_slice;
    reg  [0:0] in_last;
    wire [0:0] out_valid;
    reg  [0:0] out_ready;
    wire [47:0] out_raw;
    wire [7:0] out_exp;
    wire [15:0] out_block;
    wire [0:0] fault;
    wire [7:0] error_code;
    reg [248:0] stimulus;
    reg [82:0] expected_pre;
    reg [82:0] expected_post;
    reg [4095:0] vector_path;
    integer fd;
    integer scanned;
    integer cycles;

    xw_b1_dot128 dut (
        .clk(clk),
        .rst_n(rst_n),
        .abort(abort),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_x(in_x),
        .in_w(in_w),
        .in_mask(in_mask),
        .in_exp(in_exp),
        .in_block(in_block),
        .in_slice(in_slice),
        .in_last(in_last),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_raw(out_raw),
        .out_exp(out_exp),
        .out_block(out_block),
        .fault(fault),
        .error_code(error_code)
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
            {rst_n, abort, in_valid, in_x, in_w, in_mask, in_exp, in_block, in_slice, in_last, out_ready} = stimulus;
            #1;
            if ({in_ready, out_valid, out_raw, out_exp, out_block, fault, error_code} !== expected_pre) begin
                $display("FAIL xw_b1_dot128 PRE cycle=%0d actual=%h expected=%h", cycles, {in_ready, out_valid, out_raw, out_exp, out_block, fault, error_code}, expected_pre);
                $finish;
            end
            @(posedge clk);
            #1;
            if ({in_ready, out_valid, out_raw, out_exp, out_block, fault, error_code} !== expected_post) begin
                $display("FAIL xw_b1_dot128 NBA cycle=%0d actual=%h expected=%h", cycles, {in_ready, out_valid, out_raw, out_exp, out_block, fault, error_code}, expected_post);
                $finish;
            end
            cycles = cycles + 1;
        end
        $fclose(fd);
        if (cycles < 5) begin $display("FAIL empty vectors"); $finish; end
        $display("PASS tb_xw_b1_dot128_cycle cycles=%0d", cycles);
        $finish;
    end
endmodule
