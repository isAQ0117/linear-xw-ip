`timescale 1ns / 1ps
/* 自动生成；完整比较沿前组合输出及沿后NBA，期望另经数学Golden检查。 */
module tb_xw_a2_accum48_cycle;
    /* 驱动与观测端口。 */
    reg  [0:0] clk;
    reg  [0:0] rst_n;
    reg  [0:0] abort;
    reg  [0:0] clear;
    reg  [0:0] in_valid;
    wire [0:0] in_ready;
    reg  [71:0] in_mant;
    reg  [11:0] in_exp;
    reg  [15:0] in_block;
    wire [0:0] busy;
    wire [0:0] update_valid;
    wire [47:0] state_mant;
    wire [15:0] state_exp;
    wire [15:0] out_block;
    wire [0:0] special_path;
    wire [0:0] fault;
    wire [7:0] error_code;
    reg [103:0] stimulus;
    reg [92:0] expected_pre;
    reg [92:0] expected_post;
    reg [4095:0] vector_path;
    integer fd;
    integer scanned;
    integer cycles;

    xw_a2_accum48 dut (
        .clk(clk),
        .rst_n(rst_n),
        .abort(abort),
        .clear(clear),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_mant(in_mant),
        .in_exp(in_exp),
        .in_block(in_block),
        .busy(busy),
        .update_valid(update_valid),
        .state_mant(state_mant),
        .state_exp(state_exp),
        .out_block(out_block),
        .special_path(special_path),
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
            {rst_n, abort, clear, in_valid, in_mant, in_exp, in_block} = stimulus;
            #1;
            if ({in_ready, busy, update_valid, state_mant, state_exp, out_block, special_path, fault, error_code} !== expected_pre) begin
                $display("FAIL xw_a2_accum48 PRE cycle=%0d actual=%h expected=%h", cycles, {in_ready, busy, update_valid, state_mant, state_exp, out_block, special_path, fault, error_code}, expected_pre);
                $finish;
            end
            @(posedge clk);
            #1;
            if ({in_ready, busy, update_valid, state_mant, state_exp, out_block, special_path, fault, error_code} !== expected_post) begin
                $display("FAIL xw_a2_accum48 NBA cycle=%0d actual=%h expected=%h", cycles, {in_ready, busy, update_valid, state_mant, state_exp, out_block, special_path, fault, error_code}, expected_post);
                $finish;
            end
            cycles = cycles + 1;
        end
        $fclose(fd);
        if (cycles < 5) begin $display("FAIL empty vectors"); $finish; end
        $display("PASS tb_xw_a2_accum48_cycle cycles=%0d", cycles);
        $finish;
    end
endmodule
