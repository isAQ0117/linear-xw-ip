`timescale 1ns / 1ps

/* 独立手写常量断言：边界修正、double rounding、恢复与完成沿优先级。 */
module tb_xw_stage5_review;
    /* 任务与真实Result接口。 */
    reg clk;
    reg rst_n;
    reg abort;
    reg start;
    reg retire;
    reg clean;
    reg upstream;
    reg [7:0] upstream_code;
    reg upstream_lock;
    reg [15:0] n;
    reg valid;
    wire ready;
    reg signed [47:0] mant;
    reg signed [15:0] exp;
    reg [15:0] channel;
    wire job_ready;
    wire done;
    wire visible;
    wire error;
    wire [7:0] code;
    wire locked;
    reg rd;
    wire rd_ready;
    wire rd_valid;
    wire [143:0] data;
    wire signed [7:0] shared;
    wire [7:0] mask;
    integer ticks;
    integer polarity;
    reg [143:0] expected;

    xw_stage5_ctrl #(.MAX_N(257)) dut (
        .clk(clk), .rst_n(rst_n), .abort(abort), .job_start(start), .job_ready(job_ready),
        .job_id(32'd77), .job_n(n), .retire(retire), .clean_boundary(clean),
        .upstream_fault(upstream), .upstream_code(upstream_code), .upstream_lock(upstream_lock),
        .result_valid(valid), .result_ready(ready), .result_mant(mant), .result_exp(exp),
        .result_job(32'd77), .result_channel(channel), .group_done(done), .group_job(), .group_id(),
        .group_len(), .group_exp(), .job_results_ready(visible), .error_valid(error), .error_code(code), .fault_lock(locked),
        .rd_req(rd), .rd_ready(rd_ready), .rd_word_index(16'd0), .rd_valid(rd_valid),
        .rd_data(data), .rd_exp(shared), .rd_mask(mask), .rd_index()
    );

    /* 公共时钟。 */
    always #5 clk = ~clk;

    /* 单拍任务开始，源必须保持直到真实ready采样。 */
    task launch;
        input [15:0] length;
        begin
            @(negedge clk);
            if (!job_ready) begin $display("FAIL job not ready"); $stop; end
            n = length;
            start = 1;
            @(negedge clk);
            start = 0;
        end
    endtask

    /* 有符号边界值直接驱动，不从Python向量读取期望。 */
    task send;
        input signed [47:0] m;
        input signed [15:0] e;
        input [15:0] ch;
        begin
            @(negedge clk);
            mant = m;
            exp = e;
            channel = ch;
            valid = 1;
            ticks = 0;
            @(posedge clk);
            while (!ready && ticks < 400) begin
                ticks = ticks + 1;
                @(posedge clk);
            end
            if (!ready) begin $display("FAIL Result timeout"); $stop; end
            @(negedge clk);
            valid = 0;
        end
    endtask

    /* 只在完整Job开放后读取，尾word必须逐bit一致。 */
    task read_known;
        input [143:0] value;
        input signed [7:0] exponent;
        input [7:0] lanes;
        begin
            ticks = 0;
            while (!visible && ticks < 400) begin
                @(posedge clk); #1;
                ticks = ticks + 1;
                if (error) begin $display("FAIL unexpected error %h", code); $stop; end
            end
            if (!visible) begin $display("FAIL completion timeout"); $stop; end
            @(negedge clk);
            rd = 1;
            if (!rd_ready) begin $display("FAIL read not ready"); $stop; end
            @(posedge clk); #1;
            if (!rd_valid || data !== value || shared !== exponent || mask !== lanes) begin
                $display("FAIL literal result data=%h exp=%0d mask=%h", data, shared, mask); $stop;
            end
            @(negedge clk); rd = 0; retire = 1;
            @(negedge clk); retire = 0;
        end
    endtask

    /* 同步释放由集成层负责；本TB在下降沿释放本地reset。 */
    task reset_local;
        begin
            @(negedge clk); rst_n = 0; abort = 0; upstream = 0; upstream_lock = 0;
            valid = 0; retire = 0; rd = 0; start = 0; clean = 1;
            repeat (3) @(negedge clk);
            rst_n = 1;
            @(negedge clk);
        end
    endtask

    /* 冻结常量、错误根因和完成竞争独立检查。 */
    initial begin
        clk = 0;
        rst_n = 0;
        abort = 0;
        start = 0;
        retire = 0;
        clean = 1;
        upstream = 0;
        upstream_code = 0;
        upstream_lock = 0;
        n = 0;
        valid = 0;
        mant = 0;
        exp = 0;
        channel = 0;
        rd = 0;
        reset_local;
        for (polarity = 0; polarity < 2; polarity = polarity + 1) begin
            launch(2);
            send(polarity ? -48'sd262143 : 48'sd262143, -16'sd130, 0);
            send(polarity ? -48'sd5 : 48'sd5, -16'sd131, 1);
            expected = polarity ? ((144'h3ffff << 18) | 144'h30000) : 144'h50000;
            read_known(expected, -8'sd128, 8'h03);
        end
        launch(1);
        send(-48'sd140737488355328, 16'sd96, 0);
        read_known(144'h30000, 8'sd127, 8'h01);
        launch(1);
        send(48'sd0, 16'sd32767, 0);
        read_known(144'd0, 8'sd0, 8'h01);
        launch(1);
        send(48'sd1, 16'sd32767, 0);
        wait (error);
        #1;
        if (code !== 8'h33 || locked || visible) begin $display("FAIL recoverable33"); $stop; end
        @(negedge clk); clean = 0; retire = 1;
        @(negedge clk); retire = 0;
        if (job_ready || !error) begin $display("FAIL unclean recovery allowed"); $stop; end
        @(negedge clk); clean = 1; retire = 1;
        @(negedge clk); retire = 0;
        if (!job_ready) begin $display("FAIL clean recovery refused"); $stop; end
        launch(1);
        @(negedge clk); upstream = 1; upstream_code = 8'h32;
        @(negedge clk); upstream_code = 8'h21; upstream_lock = 1;
        @(negedge clk); upstream = 0; retire = 1;
        @(negedge clk); retire = 0;
        if (!error || code !== 8'h32 || !locked || job_ready) begin $display("FAIL first error escalation"); $stop; end
        reset_local;
        launch(1);
        send(48'sd65536, 16'sd0, 0);
        wait (dut.state == 4'd4);
        @(negedge clk); abort = 1;
        @(posedge clk); #1;
        if (done || visible || !error || code !== 8'h40) begin $display("FAIL Abort versus GroupDone"); $stop; end
        $display("PASS tb_xw_stage5_review");
        $finish;
    end

    /* 所有等待都有全局失败超时。 */
    initial begin
        #200000;
        $display("FAIL review timeout");
        $stop;
    end
endmodule
