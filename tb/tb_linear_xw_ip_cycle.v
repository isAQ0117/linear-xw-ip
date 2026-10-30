`timescale 1ns / 1ps
module tb_linear_xw_ip_cycle;
    reg clk;
    reg rst_n;
    reg job_valid;
    wire job_ready;
    reg [31:0] job_id;
    reg [15:0] job_m;
    reg [15:0] job_n;
    reg [15:0] job_k;
    reg [7:0] job_m_tile;
    reg [28:0] job_weight_base;
    reg [28:0] job_scale_base;
    wire busy;
    wire status_valid;
    reg status_ready;
    wire [31:0] status_job_id;
    wire status_ok;
    wire [7:0] status_error_code;
    reg [511:0] s_axis_tdata;
    reg s_axis_tvalid;
    wire s_axis_tready;
    reg [63:0] s_axis_tkeep;
    reg s_axis_tlast;
    reg [127:0] s_axis_tuser;
    wire [511:0] m_axis_tdata;
    wire m_axis_tvalid;
    reg m_axis_tready;
    wire [63:0] m_axis_tkeep;
    wire m_axis_tlast;
    wire [127:0] m_axis_tuser;
    wire ddr_rd_req;
    wire [28:0] ddr_rd_addra;
    wire [28:0] ddr_rd_addrb;
    reg ddr_rd_rdy;
    reg [511:0] ddr_rd_data;
    reg ddr_rd_vld;
    reg inject_valid;
    reg [2:0] inject_source;
    reg [7:0] inject_code;
    wire [43:0] debug_control;
    wire [47:0] debug_pipeline;
    integer trace_fd;
    reg [8191:0] trace_path;
    reg previous_b1;
    reg previous_b2;
    reg [7:0] previous_error;
    reg previous_lock;
    integer fd;
    integer scanned;
    integer cycles;
    reg [8191:0] filename;
    reg [1381:0] stimulus;
    reg [901:0] expected_pre;
    reg [901:0] expected_post;
    linear_xw_ip #(.STATIC_DIM_MODE(0), .N_DIM(2), .K_DIM(129)) dut (.clk(clk), .rst_n(rst_n), .job_valid(job_valid), .job_ready(job_ready), .job_id(job_id), .job_m(job_m), .job_n(job_n), .job_k(job_k), .job_m_tile(job_m_tile), .job_weight_base(job_weight_base), .job_scale_base(job_scale_base), .busy(busy), .status_valid(status_valid), .status_ready(status_ready), .status_job_id(status_job_id), .status_ok(status_ok), .status_error_code(status_error_code), .s_axis_tdata(s_axis_tdata), .s_axis_tvalid(s_axis_tvalid), .s_axis_tready(s_axis_tready), .s_axis_tkeep(s_axis_tkeep), .s_axis_tlast(s_axis_tlast), .s_axis_tuser(s_axis_tuser), .m_axis_tdata(m_axis_tdata), .m_axis_tvalid(m_axis_tvalid), .m_axis_tready(m_axis_tready), .m_axis_tkeep(m_axis_tkeep), .m_axis_tlast(m_axis_tlast), .m_axis_tuser(m_axis_tuser), .ddr_rd_req(ddr_rd_req), .ddr_rd_addra(ddr_rd_addra), .ddr_rd_addrb(ddr_rd_addrb), .ddr_rd_rdy(ddr_rd_rdy), .ddr_rd_data(ddr_rd_data), .ddr_rd_vld(ddr_rd_vld));
    assign debug_control = {dut.system_release, dut.data_release, dut.scheduler.state, dut.first_error, dut.fault_lock, dut.channel, 1'b0, dut.group_index};
    assign debug_pipeline = {dut.address_generator.state, dut.rx_busy, dut.compute.state, dut.compute.block_index, dut.stage5.state, dut.output_sender.count, dut.output_sender.pending, 1'b0, dut.output_sender.issued};
    /* 仅TB诊断注入：不在生产顶层增加物理端口。 */
    always @(*) begin
        release dut.c_fault;
        release dut.c_code;
        release dut.q_fault;
        release dut.q_code;
        release dut.rx_fault;
        release dut.rx_code;
        release dut.w_fault;
        release dut.w_code;
        release dut.a_fault;
        release dut.a_code;
        if (inject_valid) begin
            case (inject_source)
                0: begin force dut.c_fault = 1'b1; force dut.c_code = inject_code; end
                1: begin force dut.q_fault = 1'b1; force dut.q_code = inject_code; end
                2: begin force dut.rx_fault = 1'b1; force dut.rx_code = inject_code; end
                3: begin force dut.w_fault = 1'b1; force dut.w_code = inject_code; end
                4: begin force dut.a_fault = 1'b1; force dut.a_code = inject_code; end
            endcase
        end
    end
    /* 仿真唯一时钟。 */
    always #5 clk = ~clk;
    initial begin
        clk=0;cycles=0;
        previous_b1=0;previous_b2=0;previous_error=0;previous_lock=0;
        if (!$value$plusargs("TRACE=%s",trace_path)) begin $display("FAIL trace path"); $stop; end
        trace_fd=$fopen(trace_path,"w");
        if (!trace_fd) begin $display("FAIL trace open"); $stop; end

        if (!$value$plusargs("VECTORS=%s",filename)) begin $display("FAIL no vector"); $stop; end
        fd=$fopen(filename,"r");
        if (!fd) begin $display("FAIL open"); $stop; end
        while (!$feof(fd)) begin
            scanned=$fscanf(fd,"%h %h %h\n",stimulus,expected_pre,expected_post);
            if (scanned!=3) begin $display("FAIL malformed"); $stop; end
            @(negedge clk);
            {rst_n, job_valid, job_id, job_m, job_n, job_k, job_m_tile, job_weight_base, job_scale_base, status_ready, s_axis_tdata, s_axis_tvalid, s_axis_tkeep, s_axis_tlast, s_axis_tuser, m_axis_tready, ddr_rd_rdy, ddr_rd_data, ddr_rd_vld, inject_valid, inject_source, inject_code}=stimulus;
            #1;
            if ({job_ready, busy, status_valid, status_job_id, status_ok, status_error_code, s_axis_tready, m_axis_tdata, m_axis_tvalid, m_axis_tkeep, m_axis_tlast, m_axis_tuser, ddr_rd_req, ddr_rd_addra, ddr_rd_addrb, debug_control, debug_pipeline} !== expected_pre) begin
                $display("FAIL PRE cycle=%0d actual=%h expected=%h",cycles,{job_ready, busy, status_valid, status_job_id, status_ok, status_error_code, s_axis_tready, m_axis_tdata, m_axis_tvalid, m_axis_tkeep, m_axis_tlast, m_axis_tuser, ddr_rd_req, ddr_rd_addra, ddr_rd_addrb, debug_control, debug_pipeline},expected_pre); $stop;
            end
            @(posedge clk);
            if (dut.system_rst_n) begin
                if (job_valid && job_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"JOB_ACCEPT\",\"job_id\":%0d,\"row\":%0d}", cycles, job_id, 16'd0);
                if (s_axis_tvalid && s_axis_tready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"AXIS_IN_ACCEPT\",\"job_id\":%0d,\"row\":%0d,\"group\":%0d,\"index\":%0d}", cycles, dut.active_id, 16'd0, s_axis_tuser[56:48], s_axis_tuser[87:80]);
                if (ddr_rd_req)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"DDR_REQ_ACCEPT\",\"job_id\":%0d,\"row\":%0d,\"group\":%0d,\"channel\":%0d,\"kind\":%0d,\"start\":%0d,\"end\":%0d,\"beats\":%0d}", cycles, dut.active_id, 16'd0, dut.group_index, dut.channel, dut.cmd_kind, ddr_rd_addra, ddr_rd_addrb, dut.cmd_beats);
                if (ddr_rd_vld)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"DDR_BEAT\",\"job_id\":%0d,\"row\":%0d,\"group\":%0d,\"channel\":%0d,\"index\":%0d,\"data_hex\":\"%h\"}", cycles, dut.active_id, 16'd0, dut.group_index, dut.channel, ddr_rd_req ? 16'd0 : dut.receiver.received_count, ddr_rd_data);
                if (dut.load_valid && dut.load_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"LOAD_ACCEPT\",\"job_id\":%0d,\"row\":%0d,\"kind\":%0d,\"index\":%0d}", cycles, dut.active_id, 16'd0, dut.load_kind, dut.load_index);
                if (dut.compute_valid && dut.compute_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"COMPUTE_ACCEPT\",\"job_id\":%0d,\"row\":%0d,\"channel\":%0d}", cycles, dut.active_id, 16'd0, dut.channel);
                if (dut.result_valid && dut.c_result_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RESULT_ACCEPT\",\"job_id\":%0d,\"row\":%0d,\"channel\":%0d,\"mant\":%0d,\"exp\":%0d}", cycles, dut.active_id, 16'd0, dut.channel, $signed(dut.result_mant), $signed(dut.result_exp));
                if (dut.output_start && dut.output_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"OUTPUT_START\",\"job_id\":%0d,\"row\":%0d}", cycles, dut.active_id, 16'd0);
                if (m_axis_tvalid && m_axis_tready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"AXIS_OUT_ACCEPT\",\"job_id\":%0d,\"row\":%0d,\"group\":%0d,\"index\":%0d,\"data_hex\":\"%h\",\"keep_hex\":\"%h\",\"last\":%0d,\"user_hex\":\"%h\"}", cycles, dut.active_id, 16'd0, m_axis_tuser[56:48], m_axis_tuser[87:80], m_axis_tdata, m_axis_tkeep, m_axis_tlast, m_axis_tuser);
                if (status_valid && status_ready)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"STATUS_ACCEPT\",\"job_id\":%0d,\"row\":%0d,\"status_id\":%0d,\"ok\":%0d,\"code\":%0d}", cycles, dut.active_id, 16'd0, status_job_id, status_ok, status_error_code);
            end
            #1;
            if ({job_ready, busy, status_valid, status_job_id, status_ok, status_error_code, s_axis_tready, m_axis_tdata, m_axis_tvalid, m_axis_tkeep, m_axis_tlast, m_axis_tuser, ddr_rd_req, ddr_rd_addra, ddr_rd_addrb, debug_control, debug_pipeline} !== expected_post) begin
                $display("FAIL NBA cycle=%0d actual=%h expected=%h",cycles,{job_ready, busy, status_valid, status_job_id, status_ok, status_error_code, s_axis_tready, m_axis_tdata, m_axis_tvalid, m_axis_tkeep, m_axis_tlast, m_axis_tuser, ddr_rd_req, ddr_rd_addra, ddr_rd_addrb, debug_control, debug_pipeline},expected_post); $stop;
            end
            if (dut.system_rst_n) begin
                if (dut.range_done)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"RANGE_DONE\",\"job_id\":%0d,\"row\":%0d,\"group\":%0d,\"channel\":%0d,\"index\":%0d}", cycles, dut.active_id, 16'd0, dut.group_index, dut.channel, dut.word_index);
                if (dut.compute.b1_valid && !previous_b1)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"B1_VALID\",\"job_id\":%0d,\"row\":%0d,\"channel\":%0d,\"block\":%0d,\"raw\":%0d}", cycles, dut.active_id, 16'd0, dut.compute.active_channel, dut.compute.b1_block, $signed(dut.compute.b1_raw));
                if (dut.compute.b2_valid && !previous_b2)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"B2_VALID\",\"job_id\":%0d,\"row\":%0d,\"channel\":%0d,\"block\":%0d,\"term_hex\":\"%h\",\"exp\":%0d}", cycles, dut.active_id, 16'd0, dut.compute.active_channel, dut.compute.b2_block, dut.compute.b2_mant, $signed(dut.compute.b2_exp));
                if (dut.compute.a2_update)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"A2_UPDATE\",\"job_id\":%0d,\"row\":%0d,\"channel\":%0d,\"block\":%0d,\"mant\":%0d,\"exp\":%0d}", cycles, dut.active_id, 16'd0, dut.compute.active_channel, dut.compute.a2_block, $signed(dut.compute.a2_mant), $signed(dut.compute.a2_exp));
                if (dut.group_done)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"GROUP_REQUANT\",\"job_id\":%0d,\"row\":%0d,\"group\":%0d,\"length\":%0d,\"exp\":%0d}", cycles, dut.active_id, 16'd0, dut.committed_group, dut.group_len, $signed(dut.group_exp));
                if ((dut.first_error != 0 && previous_error == 0) || dut.fault_lock != previous_lock)
                    $fdisplay(trace_fd, "{\"cycle\":%0d,\"event\":\"FAULT\",\"job_id\":%0d,\"row\":%0d,\"code\":%0d,\"lock\":%0d,\"owned\":%0d}", cycles, dut.active_id, 16'd0, dut.first_error != 0 ? dut.first_error : dut.raw_code, dut.fault_lock, dut.busy);
            end
            previous_b1=dut.compute.b1_valid;
            previous_b2=dut.compute.b2_valid;
            previous_error=dut.first_error;
            previous_lock=dut.fault_lock;
            cycles=cycles+1;
        end
        if (cycles<5) begin $display("FAIL empty"); $stop; end
        $display("PASS tb_linear_xw_ip_cycle cycles=%0d",cycles);$finish;
    end
endmodule
