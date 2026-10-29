`timescale 1ns / 1ps
/* 自动生成：下降沿驱动，上升沿前后逐拍检查；vvp -N使$stop非零退出。 */
module tb_xw_bfp18_requant_cycle;
    /* 全端口驱动与期望。 */
    reg  [0:0] clk;
    reg  [0:0] rst_n;
    reg  [0:0] cancel;
    reg  [0:0] start;
    reg  [7:0] group_len;
    reg  [0:0] nonzero;
    reg  [17:0] hmax;
    wire [0:0] rd_req;
    wire [6:0] rd_index;
    reg  [0:0] rd_valid;
    reg  [47:0] rd_mant;
    reg  [15:0] rd_exp;
    wire [0:0] attempt_begin;
    wire [0:0] q_valid;
    wire [6:0] q_index;
    wire [18:0] q_mant;
    wire [0:0] q_last;
    wire [0:0] done;
    wire [7:0] shared_exp;
    wire [0:0] retried;
    wire [0:0] fault;
    wire [7:0] error_code;
    reg [94:0] stimulus;
    reg [55:0] expected_pre;
    reg [55:0] expected_post;
    reg [4095:0] vector_path;
    integer fd;
    integer scanned;
    integer cycles;

    xw_bfp18_requant dut (
        .clk(clk),
        .rst_n(rst_n),
        .cancel(cancel),
        .start(start),
        .group_len(group_len),
        .nonzero(nonzero),
        .hmax(hmax),
        .rd_req(rd_req),
        .rd_index(rd_index),
        .rd_valid(rd_valid),
        .rd_mant(rd_mant),
        .rd_exp(rd_exp),
        .attempt_begin(attempt_begin),
        .q_valid(q_valid),
        .q_index(q_index),
        .q_mant(q_mant),
        .q_last(q_last),
        .done(done),
        .shared_exp(shared_exp),
        .retried(retried),
        .fault(fault),
        .error_code(error_code)
    );

    /* 公共时钟。 */
    always #5 clk = ~clk;

    /* 仿真级硬超时。 */
    initial begin
        #100000000;
        $display("FAIL timeout");
        $stop;
    end

    /* 同时比较所有公开输出，不能将软件PASS充当HDL结果。 */
    initial begin
        clk = 0;
        rst_n = 1;
        cycles = 0;
        if (!$value$plusargs("VECTORS=%s", vector_path)) begin
            $display("FAIL missing VECTORS"); $stop;
        end
        fd = $fopen(vector_path, "r");
        if (!fd) begin $display("FAIL vector open"); $stop; end
        while (!$feof(fd)) begin
            scanned = $fscanf(fd, "%h %h %h\n", stimulus, expected_pre, expected_post);
            if (scanned != 3) begin $display("FAIL malformed vectors"); $stop; end
            @(negedge clk);
            {rst_n, cancel, start, group_len, nonzero, hmax, rd_valid, rd_mant, rd_exp} = stimulus;
            #1;
            if ({rd_req, rd_index, attempt_begin, q_valid, q_index, q_mant, q_last, done, shared_exp, retried, fault, error_code} !== expected_pre) begin
                $display("FAIL xw_bfp18_requant PRE cycle=%0d actual=%h expected=%h", cycles, {rd_req, rd_index, attempt_begin, q_valid, q_index, q_mant, q_last, done, shared_exp, retried, fault, error_code}, expected_pre);
                $stop;
            end
            @(posedge clk);
            #1;
            if ({rd_req, rd_index, attempt_begin, q_valid, q_index, q_mant, q_last, done, shared_exp, retried, fault, error_code} !== expected_post) begin
                $display("FAIL xw_bfp18_requant NBA cycle=%0d actual=%h expected=%h", cycles, {rd_req, rd_index, attempt_begin, q_valid, q_index, q_mant, q_last, done, shared_exp, retried, fault, error_code}, expected_post);
                $stop;
            end
            cycles = cycles + 1;
        end
        $fclose(fd);
        if (cycles < 5) begin $display("FAIL empty vectors"); $stop; end
        $display("PASS tb_xw_bfp18_requant_cycle cycles=%0d", cycles);
        $finish;
    end
endmodule
