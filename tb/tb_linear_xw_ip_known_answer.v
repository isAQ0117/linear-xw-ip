`timescale 1ns / 1ps

/* 独立手写端到端常量：1×1，X=1，FP8=1，Scale=1，输出65536×2^-16。 */
module tb_linear_xw_ip_known_answer;
    reg clk;
    reg rst_n;
    reg job_valid;
    wire job_ready;
    wire busy;
    wire status_valid;
    reg status_ready;
    wire [31:0] status_job_id;
    wire status_ok;
    wire [7:0] status_error_code;
    reg s_axis_tvalid;
    wire s_axis_tready;
    wire [511:0] m_axis_tdata;
    wire m_axis_tvalid;
    reg m_axis_tready;
    wire [63:0] m_axis_tkeep;
    wire m_axis_tlast;
    wire [127:0] m_axis_tuser;
    wire ddr_rd_req;
    wire [28:0] ddr_rd_addra;
    wire [28:0] ddr_rd_addrb;
    wire [511:0] ddr_rd_data;
    wire [127:0] input_user;
    wire [127:0] output_user;
    reg [705:0] held;
    reg stalled;
    integer cycles;
    integer inputs;
    integer requests;
    integer outputs;
    integer statuses;
    integer last_output;

    assign input_user = {24'd0, 8'hb2, 7'd0, 1'b1, 8'd0, 8'd1, 8'd0, 7'd0, 9'd0, 16'd0, 32'h1234};
    assign output_user = {24'd0, 8'hb2, 7'd0, 1'b1, 8'd0, 8'd1, 8'hf0, 7'd0, 9'd0, 16'd0, 32'h1234};
    assign ddr_rd_data = ddr_rd_addra == 0 ? 512'h38 : 512'h3f800000;

    linear_xw_ip #(.STATIC_DIM_MODE(1), .N_DIM(1), .K_DIM(1), .MAX_N(2), .MAX_K(129)) dut (
        .clk(clk), .rst_n(rst_n), .job_valid(job_valid), .job_ready(job_ready), .job_id(32'h1234),
        .job_m(16'd1), .job_n(16'd0), .job_k(16'd0), .job_m_tile(8'd1), .job_weight_base(29'd0), .job_scale_base(29'd8),
        .busy(busy), .status_valid(status_valid), .status_ready(status_ready), .status_job_id(status_job_id), .status_ok(status_ok), .status_error_code(status_error_code),
        .s_axis_tdata(512'd1), .s_axis_tvalid(s_axis_tvalid), .s_axis_tready(s_axis_tready), .s_axis_tkeep(64'd7), .s_axis_tlast(1'b1), .s_axis_tuser(input_user),
        .m_axis_tdata(m_axis_tdata), .m_axis_tvalid(m_axis_tvalid), .m_axis_tready(m_axis_tready), .m_axis_tkeep(m_axis_tkeep), .m_axis_tlast(m_axis_tlast), .m_axis_tuser(m_axis_tuser),
        .ddr_rd_req(ddr_rd_req), .ddr_rd_addra(ddr_rd_addra), .ddr_rd_addrb(ddr_rd_addrb), .ddr_rd_rdy(1'b1), .ddr_rd_data(ddr_rd_data), .ddr_rd_vld(ddr_rd_req)
    );

    /* 唯一仿真时钟。 */
    always #5 clk = ~clk;

    /* 独立沿前协议计数；失败使用stop，由vvp -N返回非零。 */
    always @(posedge clk) begin
        if (rst_n) begin
            cycles = cycles + 1;
            if (cycles > 5000) begin $display("FAIL watchdog"); $stop; end
            if (s_axis_tvalid && s_axis_tready)
                inputs = inputs + 1;
            if (ddr_rd_req) begin
                if (ddr_rd_addra != ddr_rd_addrb || (ddr_rd_addra != 0 && ddr_rd_addra != 8)) begin
                    $display("FAIL range"); $stop;
                end
                requests = requests + 1;
            end
            if (m_axis_tvalid) begin
                if (m_axis_tdata !== 512'd65536 || m_axis_tkeep !== 64'd7 || m_axis_tlast !== 1'b1 || m_axis_tuser !== output_user) begin
                    $display("FAIL known BFP18 answer"); $stop;
                end
            end
            if (stalled && {m_axis_tvalid, m_axis_tdata, m_axis_tkeep, m_axis_tlast, m_axis_tuser} !== held) begin
                $display("FAIL AXIS stability"); $stop;
            end
            held = {m_axis_tvalid, m_axis_tdata, m_axis_tkeep, m_axis_tlast, m_axis_tuser};
            stalled = m_axis_tvalid && !m_axis_tready;
            if (m_axis_tvalid && m_axis_tready) begin
                outputs = outputs + 1;
                last_output = cycles;
            end
            if (status_valid) begin
                if (outputs != statuses + 1 || cycles <= last_output || status_job_id !== 32'h1234 || status_ok !== 1'b1 || status_error_code !== 8'd0 || !busy || job_ready) begin
                    $display("FAIL status ordering/payload"); $stop;
                end
            end
            if (status_valid && status_ready)
                statuses = statuses + 1;
        end
    end

    initial begin
        clk=0;rst_n=0;job_valid=0;s_axis_tvalid=0;m_axis_tready=0;status_ready=0;
        cycles=0;inputs=0;requests=0;outputs=0;statuses=0;stalled=0;held=0;last_output=-1;
        repeat (3) @(negedge clk);
        rst_n=1;
        while (!job_ready) @(negedge clk);
        job_valid=1;
        @(posedge clk);
        @(negedge clk);
        job_valid=0;s_axis_tvalid=1;
        while (!s_axis_tready) @(negedge clk);
        @(posedge clk);
        @(negedge clk);
        s_axis_tvalid=0;
        wait (m_axis_tvalid);
        repeat (100) @(negedge clk);
        if (status_valid) begin $display("FAIL premature success"); $stop; end
        m_axis_tready=1;
        wait (status_valid);
        repeat (40) @(negedge clk);
        status_ready=1;
        @(posedge clk);
        @(negedge clk);
        status_ready=0;
        repeat (10) @(negedge clk);
        if (inputs != 1 || requests != 2 || outputs != 1 || statuses != 1 || busy || status_valid || !job_ready) begin
            $display("FAIL counts/release"); $stop;
        end
        /* 第二Job：Status Ready从开始即为1，验证最早终态接受边界。 */
        status_ready=1;job_valid=1;
        @(posedge clk);
        @(negedge clk);
        job_valid=0;s_axis_tvalid=1;
        while (!s_axis_tready) @(negedge clk);
        @(posedge clk);
        @(negedge clk);
        s_axis_tvalid=0;
        wait (statuses == 2);
        repeat (10) @(negedge clk);
        if (inputs != 2 || requests != 4 || outputs != 2 || statuses != 2 || busy || status_valid || !job_ready) begin
            $display("FAIL second Job/earliest status"); $stop;
        end
        $display("PASS tb_linear_xw_ip_known_answer");$finish;
    end
endmodule
