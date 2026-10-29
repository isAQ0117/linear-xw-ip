`timescale 1ns / 1ps
/* 自动生成：下降沿驱动，上升沿前后逐拍检查；vvp -N使$stop非零退出。 */
module tb_xw_result_buffer_cycle;
    parameter integer TEST_MAX_N = 12288;
    /* 全端口驱动与期望。 */
    reg  [0:0] clk;
    reg  [0:0] rst_n;
    reg  [0:0] cancel;
    reg  [0:0] job_begin;
    reg  [15:0] job_n;
    reg  [0:0] attempt_begin;
    reg  [8:0] group_index;
    reg  [7:0] group_len;
    reg  [0:0] q_valid;
    reg  [6:0] q_index;
    reg  [17:0] q_mant;
    reg  [0:0] q_last;
    reg  [0:0] commit;
    reg  [7:0] commit_exp;
    reg  [0:0] publish;
    wire [0:0] group_committed;
    wire [0:0] job_results_ready;
    reg  [0:0] rd_req;
    wire [0:0] rd_ready;
    reg  [15:0] rd_word_index;
    wire [0:0] rd_valid;
    wire [143:0] rd_data;
    wire [7:0] rd_exp;
    wire [7:0] rd_mask;
    wire [15:0] rd_index;
    wire [0:0] fault;
    reg [90:0] stimulus;
    reg [180:0] expected_pre;
    reg [180:0] expected_post;
    reg [4095:0] vector_path;
    integer fd;
    integer scanned;
    integer cycles;

    xw_result_buffer #(.MAX_N(TEST_MAX_N)) dut (
        .clk(clk),
        .rst_n(rst_n),
        .cancel(cancel),
        .job_begin(job_begin),
        .job_n(job_n),
        .attempt_begin(attempt_begin),
        .group_index(group_index),
        .group_len(group_len),
        .q_valid(q_valid),
        .q_index(q_index),
        .q_mant(q_mant),
        .q_last(q_last),
        .commit(commit),
        .commit_exp(commit_exp),
        .publish(publish),
        .group_committed(group_committed),
        .job_results_ready(job_results_ready),
        .rd_req(rd_req),
        .rd_ready(rd_ready),
        .rd_word_index(rd_word_index),
        .rd_valid(rd_valid),
        .rd_data(rd_data),
        .rd_exp(rd_exp),
        .rd_mask(rd_mask),
        .rd_index(rd_index),
        .fault(fault)
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
            {rst_n, cancel, job_begin, job_n, attempt_begin, group_index, group_len, q_valid, q_index, q_mant, q_last, commit, commit_exp, publish, rd_req, rd_word_index} = stimulus;
            #1;
            if ({group_committed, job_results_ready, rd_ready, rd_valid, rd_data, rd_exp, rd_mask, rd_index, fault} !== expected_pre) begin
                $display("FAIL xw_result_buffer PRE cycle=%0d actual=%h expected=%h", cycles, {group_committed, job_results_ready, rd_ready, rd_valid, rd_data, rd_exp, rd_mask, rd_index, fault}, expected_pre);
                $stop;
            end
            @(posedge clk);
            #1;
            if ({group_committed, job_results_ready, rd_ready, rd_valid, rd_data, rd_exp, rd_mask, rd_index, fault} !== expected_post) begin
                $display("FAIL xw_result_buffer NBA cycle=%0d actual=%h expected=%h", cycles, {group_committed, job_results_ready, rd_ready, rd_valid, rd_data, rd_exp, rd_mask, rd_index, fault}, expected_post);
                $stop;
            end
            cycles = cycles + 1;
        end
        $fclose(fd);
        if (cycles < 5) begin $display("FAIL empty vectors"); $stop; end
        $display("PASS tb_xw_result_buffer_cycle cycles=%0d", cycles);
        $finish;
    end
endmodule
