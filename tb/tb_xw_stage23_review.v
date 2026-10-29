`timescale 1ns/1ps
// Independent directed review counterexamples; no Python-generated expectations.
module tb_xw_stage23_review;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n, cfg_begin, load_valid, abort, extra;
    wire cmd_valid, cmd_ready, req, range_done, range_error, load_done, fault;
    wire [7:0] range_code, error_code;
    wire [28:0] start_addr, end_addr;
    wire [15:0] beats;
    wire kind;
    xw_ddr_addr_gen #(.DDR_MAX_BURST_BEATS(1)) ag (
        .clk(clk), .rst_n(rst_n), .abort(abort), .cfg_begin(cfg_begin),
        .cfg_n(16'd1), .cfg_k(16'd1), .cfg_weight_base(29'd0), .cfg_scale_base(29'd8),
        .load_valid(load_valid), .load_kind(1'b1), .load_index(16'd0),
        .buffer_loaded(1'b1), .buffer_error(1'b0), .buffer_error_code(8'd0),
        .cmd_valid(cmd_valid), .cmd_ready(cmd_ready), .cmd_addr_start(start_addr),
        .cmd_addr_end(end_addr), .cmd_beats(beats), .cmd_kind(kind),
        .range_done(range_done), .range_error(range_error), .range_error_code(range_code),
        .load_done(load_done), .fault(fault), .error_code(error_code)
    );
    xw_ddr_range_rx rx (
        .clk(clk), .rst_n(rst_n), .cmd_valid(cmd_valid), .cmd_ready(cmd_ready),
        .cmd_addr_start(start_addr), .cmd_addr_end(end_addr), .cmd_beats(beats), .cmd_kind(kind),
        .ddr_rd_req(req), .ddr_rd_rdy(1'b1), .ddr_rd_vld(req || extra), .ddr_rd_data(512'd7),
        .range_done(range_done), .range_error(range_error), .range_error_code(range_code)
    );
    reg hrst, job, av;
    wire jr, ar, rv, hf;
    wire [7:0] rc;
    xw_stage23_harness #(.DDR_MAX_BURST_BEATS(1)) h (
        .clk(clk), .rst_n(hrst), .job_valid(job), .job_ready(jr),
        .job_id(32'd9), .job_m(16'd1), .job_n(16'd1), .job_k(16'd1), .job_m_tile(8'd1),
        .job_weight_base(29'd0), .job_scale_base(29'd8),
        .s_axis_tvalid(av), .s_axis_tready(ar), .s_axis_tdata(512'd7),
        .s_axis_tkeep(64'd7), .s_axis_tlast(1'b1),
        .s_axis_tuser(128'h000000b2010001000000000000000009),
        .ddr_rd_rdy(1'b1), .ddr_rd_vld(1'b0), .ddr_rd_data(512'd0),
        .object_valid(1'b0), .object_kind(1'b0), .object_index(16'd0),
        .x_rd_req(1'b0), .x_rd_index(16'd0), .scale_rd_req(1'b0), .scale_rd_index(16'd0),
        .weight_rd_req(1'b0), .weight_rd_index(16'd0), .finish_test(1'b0),
        .result_valid(rv), .result_ready(1'b0), .result_code(rc), .fault_lock(hf)
    );
    task prepare_loaded;
        begin
            @(negedge clk); rst_n=0; cfg_begin=0; load_valid=0; abort=0; extra=0;
            @(negedge clk); rst_n=1; cfg_begin=1;
            @(negedge clk); cfg_begin=0; load_valid=1;
            @(negedge clk); load_valid=0;
            wait (ag.state == 3'd5);
            @(negedge clk);
        end
    endtask
    initial begin
        #100000; $display("FAIL review TIMEOUT"); $finish;
    end
    initial begin
        rst_n=0; cfg_begin=0; load_valid=0; abort=0; extra=0;
        hrst=0; job=0; av=0;
        prepare_loaded();
        extra=1;
        @(posedge clk); #1;
        if (!range_error || range_code!==8'h21 || !ag.load_done_reg || load_done!==1'b0) begin
            $display("FAIL P0-02 same-edge extra beat / completion"); $finish;
        end
        @(negedge clk); extra=0;
        @(posedge clk); #1;
        if (!fault || error_code!==8'h21 || load_done) begin
            $display("FAIL P0-02 sticky root cause"); $finish;
        end
        $display("CHECK P0-02 extra beat and Loaded same edge: PASS");
        prepare_loaded(); abort=1; #1;
        if (load_done) begin $display("FAIL abort combinational done"); $finish; end
        @(posedge clk); #1;
        if (load_done || !fault || error_code!==8'h40) begin
            $display("FAIL abort/loaded same edge"); $finish;
        end
        prepare_loaded(); rst_n=0; #1;
        if (load_done || fault) begin $display("FAIL reset/loaded same edge"); $finish; end
        $display("CHECK Reset/Abort/Loaded/Done priority: PASS");
        @(negedge clk); hrst=1;
        wait (jr); @(negedge clk); job=1;
        @(negedge clk); job=0; av=1;
        wait (ar); @(posedge clk); @(negedge clk); av=0;
        wait (h.p_valid); @(negedge clk);
        force h.p_index=16'd1;
        @(posedge clk); #1;
        if (!h.x_fault || h.x_code!==8'h40 || h.x_loaded) begin
            $display("FAIL P0-01 activation local write classification"); $finish;
        end
        @(negedge clk); release h.p_index;
        wait (rv); #1;
        if (rc!==8'h40 || !hf) begin $display("FAIL P0-01 result root cause"); $finish; end
        $display("CHECK P0-01 invalid X write -> test result40: PASS");
        $display("PASS tb_xw_stage23_review"); $finish;
    end
endmodule
