`timescale 1ns / 1ps
module tb_xw_linear_scheduler_cycle;
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
    wire [31:0] active_id;
    wire [15:0] active_n;
    wire [15:0] active_k;
    wire [28:0] weight_base;
    wire [28:0] scale_base;
    wire [15:0] channel;
    wire [8:0] group_index;
    wire cfg_begin;
    reg cfg_done;
    reg cfg_error;
    reg [7:0] cfg_error_code;
    reg datapath_online;
    wire job_start;
    reg stage5_ready;
    reg x_loaded;
    reg input_done;
    wire x_complete;
    wire load_valid;
    reg load_ready;
    wire load_kind;
    wire [15:0] load_index;
    reg load_done;
    wire compute_valid;
    reg compute_ready;
    reg result_valid;
    reg result_ready;
    reg group_done;
    reg [8:0] committed_group;
    reg job_results_ready;
    wire output_start;
    reg output_ready;
    reg output_done;
    wire finish_valid;
    reg finish_ready;
    wire finish_ok;
    wire [7:0] finish_code;
    reg status_accept;
    reg fault_valid;
    reg [7:0] fault_code;
    reg fault_system;
    reg clean_boundary;
    wire [7:0] first_error;
    wire fault_lock;
    wire cancel_datapath;
    wire clear_datapath;
    integer fd;
    integer scanned;
    integer cycles;
    reg [8191:0] filename;
    reg [192:0] stimulus;
    reg [192:0] expected_pre;
    reg [192:0] expected_post;
    xw_linear_scheduler #(.STATIC_DIM_MODE(0), .N_DIM(2), .K_DIM(129)) dut (.clk(clk), .rst_n(rst_n), .job_valid(job_valid), .job_ready(job_ready), .job_id(job_id), .job_m(job_m), .job_n(job_n), .job_k(job_k), .job_m_tile(job_m_tile), .job_weight_base(job_weight_base), .job_scale_base(job_scale_base), .busy(busy), .active_id(active_id), .active_n(active_n), .active_k(active_k), .weight_base(weight_base), .scale_base(scale_base), .channel(channel), .group_index(group_index), .cfg_begin(cfg_begin), .cfg_done(cfg_done), .cfg_error(cfg_error), .cfg_error_code(cfg_error_code), .datapath_online(datapath_online), .job_start(job_start), .stage5_ready(stage5_ready), .x_loaded(x_loaded), .input_done(input_done), .x_complete(x_complete), .load_valid(load_valid), .load_ready(load_ready), .load_kind(load_kind), .load_index(load_index), .load_done(load_done), .compute_valid(compute_valid), .compute_ready(compute_ready), .result_valid(result_valid), .result_ready(result_ready), .group_done(group_done), .committed_group(committed_group), .job_results_ready(job_results_ready), .output_start(output_start), .output_ready(output_ready), .output_done(output_done), .finish_valid(finish_valid), .finish_ready(finish_ready), .finish_ok(finish_ok), .finish_code(finish_code), .status_accept(status_accept), .fault_valid(fault_valid), .fault_code(fault_code), .fault_system(fault_system), .clean_boundary(clean_boundary), .first_error(first_error), .fault_lock(fault_lock), .cancel_datapath(cancel_datapath), .clear_datapath(clear_datapath));
    /* 仿真唯一时钟。 */
    always #5 clk = ~clk;
    initial begin
        clk=0;cycles=0;

        if (!$value$plusargs("VECTORS=%s",filename)) begin $display("FAIL no vector"); $stop; end
        fd=$fopen(filename,"r");
        if (!fd) begin $display("FAIL open"); $stop; end
        while (!$feof(fd)) begin
            scanned=$fscanf(fd,"%h %h %h\n",stimulus,expected_pre,expected_post);
            if (scanned!=3) begin $display("FAIL malformed"); $stop; end
            @(negedge clk);
            {rst_n, job_valid, job_id, job_m, job_n, job_k, job_m_tile, job_weight_base, job_scale_base, cfg_done, cfg_error, cfg_error_code, datapath_online, stage5_ready, x_loaded, input_done, load_ready, load_done, compute_ready, result_valid, result_ready, group_done, committed_group, job_results_ready, output_ready, output_done, finish_ready, status_accept, fault_valid, fault_code, fault_system, clean_boundary}=stimulus;
            #1;
            if ({job_ready, busy, active_id, active_n, active_k, weight_base, scale_base, channel, group_index, cfg_begin, job_start, x_complete, load_valid, load_kind, load_index, compute_valid, output_start, finish_valid, finish_ok, finish_code, first_error, fault_lock, cancel_datapath, clear_datapath} !== expected_pre) begin
                $display("FAIL PRE cycle=%0d actual=%h expected=%h",cycles,{job_ready, busy, active_id, active_n, active_k, weight_base, scale_base, channel, group_index, cfg_begin, job_start, x_complete, load_valid, load_kind, load_index, compute_valid, output_start, finish_valid, finish_ok, finish_code, first_error, fault_lock, cancel_datapath, clear_datapath},expected_pre); $stop;
            end
            @(posedge clk);
            #1;
            if ({job_ready, busy, active_id, active_n, active_k, weight_base, scale_base, channel, group_index, cfg_begin, job_start, x_complete, load_valid, load_kind, load_index, compute_valid, output_start, finish_valid, finish_ok, finish_code, first_error, fault_lock, cancel_datapath, clear_datapath} !== expected_post) begin
                $display("FAIL NBA cycle=%0d actual=%h expected=%h",cycles,{job_ready, busy, active_id, active_n, active_k, weight_base, scale_base, channel, group_index, cfg_begin, job_start, x_complete, load_valid, load_kind, load_index, compute_valid, output_start, finish_valid, finish_ok, finish_code, first_error, fault_lock, cancel_datapath, clear_datapath},expected_post); $stop;
            end
            cycles=cycles+1;
        end
        if (cycles<5) begin $display("FAIL empty"); $stop; end
        $display("PASS tb_xw_linear_scheduler_cycle cycles=%0d",cycles);$finish;
    end
endmodule
