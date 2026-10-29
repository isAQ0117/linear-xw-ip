`timescale 1ns / 1ps
/* 自动生成；完整比较沿前组合输出及沿后NBA，期望另经数学Golden检查。 */
module tb_xw_stage234_harness_cycle;
    /* 驱动与观测端口。 */
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
    reg  [0:0] result_ready;
    wire [47:0] result_mant;
    wire [15:0] result_exp;
    wire [31:0] result_job;
    wire [15:0] result_channel;
    wire [0:0] error_valid;
    wire [7:0] error_code;
    wire [0:0] fault_lock;
    reg [1453:0] stimulus;
    reg [189:0] expected_pre;
    reg [189:0] expected_post;
    reg [4095:0] vector_path;
    integer fd;
    integer scanned;
    integer cycles;
    integer trace_fd;
    reg [4095:0] trace_path;
    reg previous_b1;
    reg previous_b2;
    reg previous_result;

    xw_stage234_harness dut (
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
        .error_valid(error_valid),
        .error_code(error_code),
        .fault_lock(fault_lock)
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
        previous_b1 = 0;
        previous_b2 = 0;
        previous_result = 0;
        if (!$value$plusargs("TRACE=%s", trace_path)) begin
            $display("FAIL missing TRACE"); $finish;
        end
        trace_fd = $fopen(trace_path, "w");
        if (!trace_fd) begin $display("FAIL trace open"); $finish; end
        if (!$value$plusargs("VECTORS=%s", vector_path)) begin
            $display("FAIL missing VECTORS"); $finish;
        end
        fd = $fopen(vector_path, "r");
        if (!fd) begin $display("FAIL vectors open"); $finish; end
        while (!$feof(fd)) begin
            scanned = $fscanf(fd, "%h %h %h\n", stimulus, expected_pre, expected_post);
            if (scanned != 3) begin $display("FAIL malformed vectors"); $finish; end
            @(negedge clk);
            {rst_n, abort, job_valid, job_id, job_m, job_n, job_k, job_m_tile, job_weight_base, job_scale_base, s_axis_tdata, s_axis_tvalid, s_axis_tkeep, s_axis_tlast, s_axis_tuser, ddr_rd_rdy, ddr_rd_data, ddr_rd_vld, object_valid, object_kind, object_index, compute_valid, compute_job, compute_channel, compute_k, slice_enable, result_ready} = stimulus;
            #1;
            if ({job_ready, s_axis_tready, ddr_rd_req, ddr_rd_addra, ddr_rd_addrb, object_ready, object_done, x_loaded, w_loaded, s_loaded, compute_ready, result_valid, result_mant, result_exp, result_job, result_channel, error_valid, error_code, fault_lock} !== expected_pre) begin
                $display("FAIL xw_stage234_harness PRE cycle=%0d actual=%h expected=%h", cycles, {job_ready, s_axis_tready, ddr_rd_req, ddr_rd_addra, ddr_rd_addrb, object_ready, object_done, x_loaded, w_loaded, s_loaded, compute_ready, result_valid, result_mant, result_exp, result_job, result_channel, error_valid, error_code, fault_lock}, expected_pre);
                $finish;
            end
            @(posedge clk);

            if (rst_n && dut.storage.local_rst_n) begin
                if (compute_valid && compute_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"COMPUTE_ACCEPT\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"k\":%0d}", cycles, compute_job, compute_channel, compute_channel[15:7], compute_k);
                if (dut.core.x_rd_req)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RAM_READ\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d,\"slice\":%0d,\"index\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.block_index, dut.core.issued, dut.core.x_rd_index);
                if (dut.core.b1_input && dut.core.b1_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"B1_ACCEPT\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d,\"slice\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.head_block, dut.core.head_slice);
                if (dut.core.b1_valid && dut.core.b1_out_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"B2_ACCEPT\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.b1_block);
                if (dut.core.accumulator.in_valid && dut.core.accumulator.in_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"A2_ACCEPT\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.b2_block);
                if (result_valid && result_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RESULT_ACCEPT\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d}", cycles, result_job, result_channel, result_channel[15:7]);
            end
            #1;
            if ({job_ready, s_axis_tready, ddr_rd_req, ddr_rd_addra, ddr_rd_addrb, object_ready, object_done, x_loaded, w_loaded, s_loaded, compute_ready, result_valid, result_mant, result_exp, result_job, result_channel, error_valid, error_code, fault_lock} !== expected_post) begin
                $display("FAIL xw_stage234_harness NBA cycle=%0d actual=%h expected=%h", cycles, {job_ready, s_axis_tready, ddr_rd_req, ddr_rd_addra, ddr_rd_addrb, object_ready, object_done, x_loaded, w_loaded, s_loaded, compute_ready, result_valid, result_mant, result_exp, result_job, result_channel, error_valid, error_code, fault_lock}, expected_post);
                $finish;
            end

            if (rst_n) begin
                if (dut.core.b1_valid && !previous_b1)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"B1_VALID\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d,\"raw\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.b1_block, $signed(dut.core.b1_raw));
                if (dut.core.b2_valid && !previous_b2)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"B2_VALID\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d,\"term_mant_hex\":\"%h\",\"term_exp\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.b2_block, dut.core.b2_mant, $signed(dut.core.b2_exp));
                if (dut.core.a2_update)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"A2_UPDATE\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d,\"mant\":%0d,\"exp\":%0d,\"special\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.a2_block, $signed(dut.core.a2_mant), $signed(dut.core.a2_exp), dut.core.a2_special);
            end
            if (rst_n && dut.storage.local_rst_n && result_valid && !previous_result)
                $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RESULT_VALID\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"mant\":%0d,\"exp\":%0d}", cycles, result_job, result_channel, result_channel[15:7], $signed(result_mant), $signed(result_exp));
            if (rst_n && dut.storage.local_rst_n && dut.core.active) begin
                if (dut.core.fifo_count + dut.core.pending > 4) begin
                    $display("FAIL actual FIFO reservation overflow"); $finish;
                end
                $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"FIFO_LEVEL\",\"job_id\":%0d,\"channel\":%0d,\"row\":0,\"group\":%0d,\"block\":%0d,\"count\":%0d,\"pending\":%0d}", cycles, dut.core.active_job, dut.core.active_channel, dut.core.active_channel[15:7], dut.core.block_index, dut.core.fifo_count, dut.core.pending);
            end
            previous_result = rst_n && result_valid;
            previous_b1 = rst_n && dut.core.b1_valid;
            previous_b2 = rst_n && dut.core.b2_valid;
            cycles = cycles + 1;
        end
        $fclose(fd);
        if (cycles < 5) begin $display("FAIL empty vectors"); $finish; end
        $display("PASS tb_xw_stage234_harness_cycle cycles=%0d", cycles);
        $finish;
    end
endmodule
