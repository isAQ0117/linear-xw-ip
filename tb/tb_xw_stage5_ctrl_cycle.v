`timescale 1ns / 1ps
/* 自动生成：下降沿驱动，上升沿前后逐拍检查；vvp -N使$stop非零退出。 */
module tb_xw_stage5_ctrl_cycle;
    parameter integer TEST_MAX_N = 12288;
    /* 全端口驱动与期望。 */
    reg  [0:0] clk;
    reg  [0:0] rst_n;
    reg  [0:0] abort;
    reg  [0:0] job_start;
    wire [0:0] job_ready;
    reg  [31:0] job_id;
    reg  [15:0] job_n;
    reg  [0:0] retire;
    reg  [0:0] clean_boundary;
    reg  [0:0] upstream_fault;
    reg  [7:0] upstream_code;
    reg  [0:0] upstream_lock;
    reg  [0:0] result_valid;
    wire [0:0] result_ready;
    reg  [47:0] result_mant;
    reg  [15:0] result_exp;
    reg  [31:0] result_job;
    reg  [15:0] result_channel;
    wire [0:0] group_done;
    wire [31:0] group_job;
    wire [8:0] group_id;
    wire [7:0] group_len;
    wire [7:0] group_exp;
    wire [0:0] job_results_ready;
    wire [0:0] error_valid;
    wire [7:0] error_code;
    wire [0:0] fault_lock;
    reg  [0:0] rd_req;
    wire [0:0] rd_ready;
    reg  [15:0] rd_word_index;
    wire [0:0] rd_valid;
    wire [143:0] rd_data;
    wire [7:0] rd_exp;
    wire [7:0] rd_mask;
    wire [15:0] rd_index;
    reg [192:0] stimulus;
    reg [248:0] expected_pre;
    reg [248:0] expected_post;
    reg [4095:0] vector_path;
    integer fd;
    integer scanned;
    integer cycles;
    integer trace_fd;
    reg [4095:0] trace_path;
    reg previous_visible;
    reg previous_error;

    xw_stage5_ctrl #(.MAX_N(TEST_MAX_N)) dut (
        .clk(clk),
        .rst_n(rst_n),
        .abort(abort),
        .job_start(job_start),
        .job_ready(job_ready),
        .job_id(job_id),
        .job_n(job_n),
        .retire(retire),
        .clean_boundary(clean_boundary),
        .upstream_fault(upstream_fault),
        .upstream_code(upstream_code),
        .upstream_lock(upstream_lock),
        .result_valid(result_valid),
        .result_ready(result_ready),
        .result_mant(result_mant),
        .result_exp(result_exp),
        .result_job(result_job),
        .result_channel(result_channel),
        .group_done(group_done),
        .group_job(group_job),
        .group_id(group_id),
        .group_len(group_len),
        .group_exp(group_exp),
        .job_results_ready(job_results_ready),
        .error_valid(error_valid),
        .error_code(error_code),
        .fault_lock(fault_lock),
        .rd_req(rd_req),
        .rd_ready(rd_ready),
        .rd_word_index(rd_word_index),
        .rd_valid(rd_valid),
        .rd_data(rd_data),
        .rd_exp(rd_exp),
        .rd_mask(rd_mask),
        .rd_index(rd_index)
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
        previous_visible = 0;
        previous_error = 0;
        if (!$value$plusargs("TRACE=%s", trace_path)) begin
            $display("FAIL missing TRACE"); $stop;
        end
        trace_fd = $fopen(trace_path, "w");
        if (!trace_fd) begin $display("FAIL trace open"); $stop; end
        if (!$value$plusargs("VECTORS=%s", vector_path)) begin
            $display("FAIL missing VECTORS"); $stop;
        end
        fd = $fopen(vector_path, "r");
        if (!fd) begin $display("FAIL vector open"); $stop; end
        while (!$feof(fd)) begin
            scanned = $fscanf(fd, "%h %h %h\n", stimulus, expected_pre, expected_post);
            if (scanned != 3) begin $display("FAIL malformed vectors"); $stop; end
            @(negedge clk);
            {rst_n, abort, job_start, job_id, job_n, retire, clean_boundary, upstream_fault, upstream_code, upstream_lock, result_valid, result_mant, result_exp, result_job, result_channel, rd_req, rd_word_index} = stimulus;
            #1;
            if ({job_ready, result_ready, group_done, group_job, group_id, group_len, group_exp, job_results_ready, error_valid, error_code, fault_lock, rd_ready, rd_valid, rd_data, rd_exp, rd_mask, rd_index} !== expected_pre) begin
                $display("FAIL xw_stage5_ctrl PRE cycle=%0d actual=%h expected=%h", cycles, {job_ready, result_ready, group_done, group_job, group_id, group_len, group_exp, job_results_ready, error_valid, error_code, fault_lock, rd_ready, rd_valid, rd_data, rd_exp, rd_mask, rd_index}, expected_pre);
                $stop;
            end
            @(posedge clk);

            if (rst_n) begin
                if (dut.start_accept)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"JOB_ACCEPT\",\"job_id\":%0d,\"group\":%0d,\"n\":%0d}", cycles, dut.job_id, 0, dut.job_n);
                if (dut.result_valid && dut.result_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RESULT_ACCEPT\",\"job_id\":%0d,\"group\":%0d,\"channel\":%0d,\"mant\":%0d,\"exp\":%0d}", cycles, dut.result_job, dut.result_channel >> 7, dut.result_channel, $signed(dut.result_mant), $signed(dut.result_exp));
                if (dut.attempt_begin)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"ATTEMPT_BEGIN\",\"job_id\":%0d,\"group\":%0d,\"retry\":%0d}", cycles, dut.active_job, dut.current_group, dut.quant_start ? 0 : dut.retried);
                if (dut.ram_req)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"GROUP_RAM_READ\",\"job_id\":%0d,\"group\":%0d,\"index\":%0d}", cycles, dut.active_job, dut.current_group, dut.ram_index);
                if (dut.q_valid)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"QUANT_ACCEPT\",\"job_id\":%0d,\"group\":%0d,\"index\":%0d,\"mant\":%0d,\"last\":%0d,\"retry\":%0d}", cycles, dut.active_job, dut.current_group, dut.q_index, $signed(dut.q_mant), dut.q_last, dut.retried);
                if (dut.result_buffer.write_enable)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RESULT_WORD_WRITE\",\"job_id\":%0d,\"group\":%0d,\"index\":%0d,\"data_hex\":\"%h\"}", cycles, dut.active_job, dut.current_group, dut.result_buffer.write_index, dut.result_buffer.assembled);
                if (dut.result_buffer.commit_enable)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"GROUP_COMMIT\",\"job_id\":%0d,\"group\":%0d,\"exp\":%0d}", cycles, dut.active_job, dut.current_group, $signed(dut.quant_exp));
            end
            #1;
            if ({job_ready, result_ready, group_done, group_job, group_id, group_len, group_exp, job_results_ready, error_valid, error_code, fault_lock, rd_ready, rd_valid, rd_data, rd_exp, rd_mask, rd_index} !== expected_post) begin
                $display("FAIL xw_stage5_ctrl NBA cycle=%0d actual=%h expected=%h", cycles, {job_ready, result_ready, group_done, group_job, group_id, group_len, group_exp, job_results_ready, error_valid, error_code, fault_lock, rd_ready, rd_valid, rd_data, rd_exp, rd_mask, rd_index}, expected_post);
                $stop;
            end

            if (rst_n) begin
                if (dut.q_valid)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"QUANT_VALID\",\"job_id\":%0d,\"group\":%0d,\"index\":%0d,\"mant\":%0d,\"retry\":%0d}", cycles, dut.active_job, dut.current_group, dut.q_index, $signed(dut.q_mant), dut.retried);
                if (dut.quant_done)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"REQUANT_DONE\",\"job_id\":%0d,\"group\":%0d,\"exp\":%0d}", cycles, dut.active_job, dut.current_group, $signed(dut.quant_exp));
                if (dut.rd_valid)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RESULT_READ\",\"job_id\":%0d,\"group\":%0d,\"index\":%0d,\"data_hex\":\"%h\",\"exp\":%0d,\"mask\":%0d}", cycles, dut.active_job, dut.rd_index >> 4, dut.rd_index, dut.rd_data, $signed(dut.rd_exp), dut.rd_mask);
                if (dut.group_done)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"GROUP_REQUANT\",\"job_id\":%0d,\"group\":%0d,\"length\":%0d,\"exp\":%0d}", cycles, dut.group_job, dut.group_id, dut.group_len, $signed(dut.group_exp));
                if (dut.job_results_ready && !previous_visible)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"JOB_RESULTS_READY\",\"job_id\":%0d,\"group\":%0d}", cycles, dut.active_job, dut.current_group);
                if (dut.error_valid && !previous_error)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"ERROR\",\"job_id\":%0d,\"group\":%0d,\"code\":%0d,\"lock\":%0d}", cycles, dut.active_job, dut.current_group, dut.error_code, dut.fault_lock);
            end
            previous_visible = dut.job_results_ready;
            previous_error = dut.error_valid;
            cycles = cycles + 1;
        end
        $fclose(fd);
        if (cycles < 5) begin $display("FAIL empty vectors"); $stop; end
        $display("PASS tb_xw_stage5_ctrl_cycle cycles=%0d", cycles);
        $finish;
    end
endmodule
