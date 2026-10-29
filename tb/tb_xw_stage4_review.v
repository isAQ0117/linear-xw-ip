`timescale 1ns / 1ps

/* 独立手写审查：完整指数域、ACC_RANGE传播、首错与晚到系统故障。 */
module tb_xw_stage4_review;
    /* 时钟、请求与无Ready同步RAM响应。 */
    reg clk;
    reg rst_n;
    reg req;
    reg upstream_fault;
    reg [7:0] upstream_code;
    wire ready;
    wire xr;
    wire wr;
    wire sr;
    reg xv;
    reg wv;
    reg sv;
    wire rv;
    wire ev;
    wire [7:0] ec;
    wire locked;
    integer ticks;
    reg av;
    reg acl;
    wire ar;
    wire au;
    wire af;
    wire [7:0] acode;
    wire signed [47:0] am;
    wire signed [15:0] ae;

    xw_b3b_compute_ctrl core (
        .clk(clk), .rst_n(rst_n), .abort(1'b0), .req_valid(req), .req_ready(ready),
        .req_job(32'd77), .req_channel(16'd3), .req_k(16'd128),
        .x_loaded(1'b1), .w_loaded(1'b1), .s_loaded(1'b1),
        .upstream_fault(upstream_fault), .upstream_code(upstream_code), .slice_enable(1'b1),
        .x_rd_req(xr), .x_rd_index(), .x_rd_valid(xv), .x_rd_data({8{18'd1}}), .x_rd_exp(8'd0), .x_rd_mask(8'hff),
        .w_rd_req(wr), .w_rd_index(), .w_rd_valid(wv), .w_rd_data({8{8'hb8}}), .w_rd_mask(8'hff),
        .s_rd_req(sr), .s_rd_index(), .s_rd_valid(sv), .s_rd_bits(32'h3f800000),
        .result_valid(rv), .result_ready(1'b0), .result_mant(), .result_exp(), .result_job(), .result_channel(),
        .error_valid(ev), .error_code(ec), .fault_lock(locked)
    );
    xw_a2_accum48 wide_test (
        .clk(clk), .rst_n(rst_n), .abort(1'b0), .clear(acl), .in_valid(av), .in_ready(ar),
        .in_mant(72'sd1), .in_exp(12'sd2047), .in_block(16'd9), .busy(),
        .update_valid(au), .state_mant(am), .state_exp(ae), .out_block(), .special_path(), .fault(af), .error_code(acode)
    );

    /* 公共时钟。 */
    always #5 clk = ~clk;

    /* 固定一拍registered response，禁止同沿组合旁路。 */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            xv <= 0;
            wv <= 0;
            sv <= 0;
        end else begin
            xv <= xr;
            wv <= wr;
            sv <= sr;
        end
    end

    /* 正常输入域不可能指数超界；受控注入验证不可达防御路径。 */
    initial begin
        clk = 0;
        rst_n = 0;
        req = 0;
        upstream_fault = 0;
        upstream_code = 0;
        av = 0;
        acl = 0;
        repeat (3) @(negedge clk);
        rst_n = 1;
        @(negedge clk);
        req = 1;
        @(negedge clk);
        req = 0;
        wait (core.b2_valid);
        @(negedge clk);
        force core.accumulator.state_mant = 48'h800000000000;
        force core.accumulator.state_exp = 16'sd32767;
        @(posedge clk);
        @(negedge clk);
        release core.accumulator.state_mant;
        release core.accumulator.state_exp;
        ticks = 0;
        while (!ev && ticks < 600) begin
            @(posedge clk); #1;
            if (rv) begin $display("FAIL invalid result committed"); $finish; end
            ticks = ticks + 1;
        end
        if (!ev || ec !== 8'h32 || locked || rv) begin
            $display("FAIL ACC_RANGE propagation code=%h ticks=%0d", ec, ticks); $finish;
        end
        $display("CHECK injected ACC_RANGE -> controller32, no result: PASS");
        @(negedge clk);
        upstream_fault = 1;
        upstream_code = 8'h21;
        repeat (4) @(posedge clk);
        #1;
        if (ec !== 8'h32 || !locked || rv || ready) begin
            $display("FAIL first error / later fatal escalation"); $finish;
        end
        $display("CHECK first code retained, later system fault locks: PASS");
        @(negedge clk);
        force wide_test.state_mant = -48'sd1;
        force wide_test.state_exp = -16'sd32768;
        av = 1;
        @(posedge clk);
        @(negedge clk);
        av = 0;
        release wide_test.state_mant;
        release wide_test.state_exp;
        ticks = 0;
        while (!au && ticks < 600) begin
            @(posedge clk); #1;
            ticks = ticks + 1;
        end
        if (!au || af || am !== 48'sd70368744177664 || ae !== 16'sd2001) begin
            $display("FAIL complete exponent domain mant=%0d exp=%0d fault=%b code=%h", am, ae, af, acode); $finish;
        end
        $display("CHECK signed16/signed12 exponent extremes, 546 chunks: PASS");
        /* 已发布的正确结果必须在反压和晚到故障时保持。 */
        @(negedge clk);
        rst_n = 0;
        upstream_fault = 0;
        repeat (3) @(negedge clk);
        rst_n = 1;
        @(negedge clk); req = 1;
        @(negedge clk); req = 0;
        wait (rv);
        #1;
        if (core.result_mant !== -48'sd549755813888 || core.result_exp !== -16'sd32 ||
            core.result_job !== 32'd77 || core.result_channel !== 16'd3) begin
            $display("FAIL known exact full block result"); $finish;
        end
        @(negedge clk);
        upstream_fault = 1;
        upstream_code = 8'h21;
        repeat (5) @(posedge clk);
        #1;
        if (!rv || !ev || ec !== 8'h21 || !locked ||
            core.result_mant !== -48'sd549755813888 || core.result_exp !== -16'sd32) begin
            $display("FAIL published result stability under late fault"); $finish;
        end
        $display("CHECK published result immutable during backpressure/late fault: PASS");
        /* 首次发布之前的错误则必须禁止A2提交和result。 */
        @(negedge clk);
        rst_n = 0;
        upstream_fault = 0;
        repeat (3) @(negedge clk);
        rst_n = 1;
        @(negedge clk); req = 1;
        @(negedge clk); req = 0;
        wait (core.accumulator.state == 4'd7);
        @(negedge clk);
        upstream_fault = 1;
        upstream_code = 8'h21;
        repeat (5) @(posedge clk);
        #1;
        if (rv || !ev || ec !== 8'h21 || core.a2_update) begin
            $display("FAIL pre-publication error committed invalid result"); $finish;
        end
        $display("CHECK pre-commit fatal suppresses A2/result: PASS");
        $display("PASS tb_xw_stage4_review");
        $finish;
    end

    /* 每一个等待有仿真级硬超时。 */
    initial begin
        #300000;
        $display("FAIL review TIMEOUT");
        $finish;
    end
endmodule
