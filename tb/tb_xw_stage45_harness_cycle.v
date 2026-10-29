`timescale 1ns / 1ps
/* 自动生成：下降沿驱动，上升沿前后逐拍检查；vvp -N使$stop非零退出。 */
module tb_xw_stage45_harness_cycle;
    /* 全端口驱动与期望。 */
    reg  [0:0] clk;
    reg  [0:0] rst_n;
    reg  [0:0] abort;
    reg  [0:0] job_valid;
    wire [0:0] job_ready;
    reg  [31:0] job_id;
    reg  [15:0] job_m;
    reg  [15:0] job_n;
    reg  [15:0] job_k;
    reg  [7:0] job_m_tile;
    reg  [28:0] job_weight_base;
    reg  [28:0] job_scale_base;
    reg  [511:0] s_axis_tdata;
    reg  [0:0] s_axis_tvalid;
    wire [0:0] s_axis_tready;
    reg  [63:0] s_axis_tkeep;
    reg  [0:0] s_axis_tlast;
    reg  [127:0] s_axis_tuser;
    wire [0:0] ddr_rd_req;
    wire [28:0] ddr_rd_addra;
    wire [28:0] ddr_rd_addrb;
    reg  [0:0] ddr_rd_rdy;
    reg  [511:0] ddr_rd_data;
    reg  [0:0] ddr_rd_vld;
    reg  [0:0] object_valid;
    wire [0:0] object_ready;
    reg  [0:0] object_kind;
    reg  [15:0] object_index;
    wire [0:0] object_done;
    wire [0:0] x_loaded;
    wire [0:0] w_loaded;
    wire [0:0] s_loaded;
    reg  [0:0] compute_valid;
    wire [0:0] compute_ready;
    reg  [31:0] compute_job;
    reg  [15:0] compute_channel;
    reg  [15:0] compute_k;
    reg  [0:0] slice_enable;
    wire [0:0] result_valid;
    wire [0:0] result_ready;
    wire [47:0] result_mant;
    wire [15:0] result_exp;
    wire [31:0] result_job;
    wire [15:0] result_channel;
    wire [0:0] stage4_error_valid;
    wire [7:0] stage4_error_code;
    wire [0:0] stage4_fault_lock;
    reg  [0:0] retire;
    reg  [0:0] rd_req;
    reg  [15:0] rd_word_index;
    wire [0:0] rd_ready;
    wire [0:0] rd_valid;
    wire [143:0] rd_data;
    wire [7:0] rd_exp;
    wire [7:0] rd_mask;
    wire [15:0] rd_index;
    wire [0:0] group_done;
    wire [31:0] group_job;
    wire [8:0] group_id;
    wire [7:0] group_len;
    wire [7:0] group_exp;
    wire [0:0] job_results_ready;
    wire [0:0] error_valid;
    wire [7:0] error_code;
    wire [0:0] fault_lock;
    reg [1470:0] stimulus;
    reg [437:0] expected_pre;
    reg [437:0] expected_post;
    reg [4095:0] vector_path;
    integer fd;
    integer scanned;
    integer cycles;
    integer trace_fd;
    reg [4095:0] trace_path;
    reg previous_visible;
    reg previous_error;

    xw_stage45_harness dut (
        .clk(clk),
        .rst_n(rst_n),
        .abort(abort),
        .job_valid(job_valid),
        .job_ready(job_ready),
        .job_id(job_id),
        .job_m(job_m),
        .job_n(job_n),
        .job_k(job_k),
        .job_m_tile(job_m_tile),
        .job_weight_base(job_weight_base),
        .job_scale_base(job_scale_base),
        .s_axis_tdata(s_axis_tdata),
        .s_axis_tvalid(s_axis_tvalid),
        .s_axis_tready(s_axis_tready),
        .s_axis_tkeep(s_axis_tkeep),
        .s_axis_tlast(s_axis_tlast),
        .s_axis_tuser(s_axis_tuser),
        .ddr_rd_req(ddr_rd_req),
        .ddr_rd_addra(ddr_rd_addra),
        .ddr_rd_addrb(ddr_rd_addrb),
        .ddr_rd_rdy(ddr_rd_rdy),
        .ddr_rd_data(ddr_rd_data),
        .ddr_rd_vld(ddr_rd_vld),
        .object_valid(object_valid),
        .object_ready(object_ready),
        .object_kind(object_kind),
        .object_index(object_index),
        .object_done(object_done),
        .x_loaded(x_loaded),
        .w_loaded(w_loaded),
        .s_loaded(s_loaded),
        .compute_valid(compute_valid),
        .compute_ready(compute_ready),
        .compute_job(compute_job),
        .compute_channel(compute_channel),
        .compute_k(compute_k),
        .slice_enable(slice_enable),
        .result_valid(result_valid),
        .result_ready(result_ready),
        .result_mant(result_mant),
        .result_exp(result_exp),
        .result_job(result_job),
        .result_channel(result_channel),
        .stage4_error_valid(stage4_error_valid),
        .stage4_error_code(stage4_error_code),
        .stage4_fault_lock(stage4_fault_lock),
        .retire(retire),
        .rd_req(rd_req),
        .rd_word_index(rd_word_index),
        .rd_ready(rd_ready),
        .rd_valid(rd_valid),
        .rd_data(rd_data),
        .rd_exp(rd_exp),
        .rd_mask(rd_mask),
        .rd_index(rd_index),
        .group_done(group_done),
        .group_job(group_job),
        .group_id(group_id),
        .group_len(group_len),
        .group_exp(group_exp),
        .job_results_ready(job_results_ready),
        .error_valid(error_valid),
        .error_code(error_code),
        .fault_lock(fault_lock)
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
            {rst_n, abort, job_valid, job_id, job_m, job_n, job_k, job_m_tile, job_weight_base, job_scale_base, s_axis_tdata, s_axis_tvalid, s_axis_tkeep, s_axis_tlast, s_axis_tuser, ddr_rd_rdy, ddr_rd_data, ddr_rd_vld, object_valid, object_kind, object_index, compute_valid, compute_job, compute_channel, compute_k, slice_enable, retire, rd_req, rd_word_index} = stimulus;
            #1;
            if ({job_ready, s_axis_tready, ddr_rd_req, ddr_rd_addra, ddr_rd_addrb, object_ready, object_done, x_loaded, w_loaded, s_loaded, compute_ready, result_valid, result_ready, result_mant, result_exp, result_job, result_channel, stage4_error_valid, stage4_error_code, stage4_fault_lock, rd_ready, rd_valid, rd_data, rd_exp, rd_mask, rd_index, group_done, group_job, group_id, group_len, group_exp, job_results_ready, error_valid, error_code, fault_lock} !== expected_pre) begin
                $display("FAIL xw_stage45_harness PRE cycle=%0d actual=%h expected=%h", cycles, {job_ready, s_axis_tready, ddr_rd_req, ddr_rd_addra, ddr_rd_addrb, object_ready, object_done, x_loaded, w_loaded, s_loaded, compute_ready, result_valid, result_ready, result_mant, result_exp, result_job, result_channel, stage4_error_valid, stage4_error_code, stage4_fault_lock, rd_ready, rd_valid, rd_data, rd_exp, rd_mask, rd_index, group_done, group_job, group_id, group_len, group_exp, job_results_ready, error_valid, error_code, fault_lock}, expected_pre);
                $stop;
            end
            @(posedge clk);

            if (rst_n) begin
                if (dut.stage5.start_accept)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"JOB_ACCEPT\",\"job_id\":%0d,\"group\":%0d,\"n\":%0d}", cycles, dut.stage5.job_id, 0, dut.stage5.job_n);
                if (dut.stage5.result_valid && dut.stage5.result_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RESULT_ACCEPT\",\"job_id\":%0d,\"group\":%0d,\"channel\":%0d,\"mant\":%0d,\"exp\":%0d}", cycles, dut.stage5.result_job, dut.stage5.result_channel >> 7, dut.stage5.result_channel, $signed(dut.stage5.result_mant), $signed(dut.stage5.result_exp));
                if (dut.stage5.attempt_begin)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"ATTEMPT_BEGIN\",\"job_id\":%0d,\"group\":%0d,\"retry\":%0d}", cycles, dut.stage5.active_job, dut.stage5.current_group, dut.stage5.quant_start ? 0 : dut.stage5.retried);
                if (dut.stage5.ram_req)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"GROUP_RAM_READ\",\"job_id\":%0d,\"group\":%0d,\"index\":%0d}", cycles, dut.stage5.active_job, dut.stage5.current_group, dut.stage5.ram_index);
                if (dut.stage5.q_valid)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"QUANT_ACCEPT\",\"job_id\":%0d,\"group\":%0d,\"index\":%0d,\"mant\":%0d,\"last\":%0d,\"retry\":%0d}", cycles, dut.stage5.active_job, dut.stage5.current_group, dut.stage5.q_index, $signed(dut.stage5.q_mant), dut.stage5.q_last, dut.stage5.retried);
                if (dut.stage5.result_buffer.write_enable)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RESULT_WORD_WRITE\",\"job_id\":%0d,\"group\":%0d,\"index\":%0d,\"data_hex\":\"%h\"}", cycles, dut.stage5.active_job, dut.stage5.current_group, dut.stage5.result_buffer.write_index, dut.stage5.result_buffer.assembled);
                if (dut.stage5.result_buffer.commit_enable)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"GROUP_COMMIT\",\"job_id\":%0d,\"group\":%0d,\"exp\":%0d}", cycles, dut.stage5.active_job, dut.stage5.current_group, $signed(dut.stage5.quant_exp));
            end
            #1;
            if ({job_ready, s_axis_tready, ddr_rd_req, ddr_rd_addra, ddr_rd_addrb, object_ready, object_done, x_loaded, w_loaded, s_loaded, compute_ready, result_valid, result_ready, result_mant, result_exp, result_job, result_channel, stage4_error_valid, stage4_error_code, stage4_fault_lock, rd_ready, rd_valid, rd_data, rd_exp, rd_mask, rd_index, group_done, group_job, group_id, group_len, group_exp, job_results_ready, error_valid, error_code, fault_lock} !== expected_post) begin
                $display("FAIL xw_stage45_harness NBA cycle=%0d actual=%h expected=%h", cycles, {job_ready, s_axis_tready, ddr_rd_req, ddr_rd_addra, ddr_rd_addrb, object_ready, object_done, x_loaded, w_loaded, s_loaded, compute_ready, result_valid, result_ready, result_mant, result_exp, result_job, result_channel, stage4_error_valid, stage4_error_code, stage4_fault_lock, rd_ready, rd_valid, rd_data, rd_exp, rd_mask, rd_index, group_done, group_job, group_id, group_len, group_exp, job_results_ready, error_valid, error_code, fault_lock}, expected_post);
                $stop;
            end

            if (rst_n) begin
                if (dut.stage5.q_valid)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"QUANT_VALID\",\"job_id\":%0d,\"group\":%0d,\"index\":%0d,\"mant\":%0d,\"retry\":%0d}", cycles, dut.stage5.active_job, dut.stage5.current_group, dut.stage5.q_index, $signed(dut.stage5.q_mant), dut.stage5.retried);
                if (dut.stage5.quant_done)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"REQUANT_DONE\",\"job_id\":%0d,\"group\":%0d,\"exp\":%0d}", cycles, dut.stage5.active_job, dut.stage5.current_group, $signed(dut.stage5.quant_exp));
                if (dut.stage5.rd_valid)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RESULT_READ\",\"job_id\":%0d,\"group\":%0d,\"index\":%0d,\"data_hex\":\"%h\",\"exp\":%0d,\"mask\":%0d}", cycles, dut.stage5.active_job, dut.stage5.rd_index >> 4, dut.stage5.rd_index, dut.stage5.rd_data, $signed(dut.stage5.rd_exp), dut.stage5.rd_mask);
                if (dut.stage5.group_done)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"GROUP_REQUANT\",\"job_id\":%0d,\"group\":%0d,\"length\":%0d,\"exp\":%0d}", cycles, dut.stage5.group_job, dut.stage5.group_id, dut.stage5.group_len, $signed(dut.stage5.group_exp));
                if (dut.stage5.job_results_ready && !previous_visible)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"JOB_RESULTS_READY\",\"job_id\":%0d,\"group\":%0d}", cycles, dut.stage5.active_job, dut.stage5.current_group);
                if (dut.stage5.error_valid && !previous_error)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"ERROR\",\"job_id\":%0d,\"group\":%0d,\"code\":%0d,\"lock\":%0d}", cycles, dut.stage5.active_job, dut.stage5.current_group, dut.stage5.error_code, dut.stage5.fault_lock);
            end
            previous_visible = dut.stage5.job_results_ready;
            previous_error = dut.stage5.error_valid;
            cycles = cycles + 1;
        end
        $fclose(fd);
        if (cycles < 5) begin $display("FAIL empty vectors"); $stop; end
        $display("PASS tb_xw_stage45_harness_cycle cycles=%0d", cycles);
        $finish;
    end
endmodule
