`timescale 1ns / 1ps
/* 自动生成：下降沿驱动，上升沿前后逐拍检查；vvp -N使$stop非零退出。 */
module tb_xw_output_group_buffer_cycle;
    /* 全端口驱动与期望。 */
    reg  [0:0] clk;
    reg  [0:0] rst_n;
    reg  [0:0] cancel;
    reg  [0:0] begin_group;
    reg  [31:0] group_job;
    reg  [15:0] group_base;
    reg  [7:0] group_len;
    reg  [0:0] result_valid;
    wire [0:0] result_ready;
    reg  [47:0] result_mant;
    reg  [15:0] result_exp;
    reg  [31:0] result_job;
    reg  [15:0] result_channel;
    wire [0:0] loaded;
    wire [0:0] nonzero;
    wire [17:0] hmax;
    reg  [0:0] rd_req;
    reg  [6:0] rd_index;
    wire [0:0] rd_valid;
    wire [47:0] rd_mant;
    wire [15:0] rd_exp;
    wire [0:0] fault;
    reg [179:0] stimulus;
    reg [86:0] expected_pre;
    reg [86:0] expected_post;
    reg [4095:0] vector_path;
    integer fd;
    integer scanned;
    integer cycles;

    xw_output_group_buffer dut (
        .clk(clk),
        .rst_n(rst_n),
        .cancel(cancel),
        .begin_group(begin_group),
        .group_job(group_job),
        .group_base(group_base),
        .group_len(group_len),
        .result_valid(result_valid),
        .result_ready(result_ready),
        .result_mant(result_mant),
        .result_exp(result_exp),
        .result_job(result_job),
        .result_channel(result_channel),
        .loaded(loaded),
        .nonzero(nonzero),
        .hmax(hmax),
        .rd_req(rd_req),
        .rd_index(rd_index),
        .rd_valid(rd_valid),
        .rd_mant(rd_mant),
        .rd_exp(rd_exp),
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
            {rst_n, cancel, begin_group, group_job, group_base, group_len, result_valid, result_mant, result_exp, result_job, result_channel, rd_req, rd_index} = stimulus;
            #1;
            if ({result_ready, loaded, nonzero, hmax, rd_valid, rd_mant, rd_exp, fault} !== expected_pre) begin
                $display("FAIL xw_output_group_buffer PRE cycle=%0d actual=%h expected=%h", cycles, {result_ready, loaded, nonzero, hmax, rd_valid, rd_mant, rd_exp, fault}, expected_pre);
                $stop;
            end
            @(posedge clk);
            #1;
            if ({result_ready, loaded, nonzero, hmax, rd_valid, rd_mant, rd_exp, fault} !== expected_post) begin
                $display("FAIL xw_output_group_buffer NBA cycle=%0d actual=%h expected=%h", cycles, {result_ready, loaded, nonzero, hmax, rd_valid, rd_mant, rd_exp, fault}, expected_post);
                $stop;
            end
            cycles = cycles + 1;
        end
        $fclose(fd);
        if (cycles < 5) begin $display("FAIL empty vectors"); $stop; end
        $display("PASS tb_xw_output_group_buffer_cycle cycles=%0d", cycles);
        $finish;
    end
endmodule
