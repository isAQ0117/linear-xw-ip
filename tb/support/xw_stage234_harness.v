`timescale 1ns / 1ps

/* TEST ONLY：原Stage23完整装载Harness的读端连接Stage4，不是Stage7 Scheduler。 */
module xw_stage234_harness (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                abort,
    input  wire                job_valid,
    output wire                job_ready,
    input  wire [31:0]          job_id,
    input  wire [15:0]          job_m,
    input  wire [15:0]          job_n,
    input  wire [15:0]          job_k,
    input  wire [7:0]           job_m_tile,
    input  wire [28:0]          job_weight_base,
    input  wire [28:0]          job_scale_base,
    input  wire [511:0]         s_axis_tdata,
    input  wire                s_axis_tvalid,
    output wire                s_axis_tready,
    input  wire [63:0]          s_axis_tkeep,
    input  wire                s_axis_tlast,
    input  wire [127:0]         s_axis_tuser,
    output wire                ddr_rd_req,
    output wire [28:0]          ddr_rd_addra,
    output wire [28:0]          ddr_rd_addrb,
    input  wire                ddr_rd_rdy,
    input  wire [511:0]         ddr_rd_data,
    input  wire                ddr_rd_vld,
    input  wire                object_valid,
    output wire                object_ready,
    input  wire                object_kind,
    input  wire [15:0]          object_index,
    output wire                object_done,
    output wire                x_loaded,
    output wire                w_loaded,
    output wire                s_loaded,
    input  wire                compute_valid,
    output wire                compute_ready,
    input  wire [31:0]          compute_job,
    input  wire [15:0]          compute_channel,
    input  wire [15:0]          compute_k,
    input  wire                slice_enable,
    output wire                result_valid,
    input  wire                result_ready,
    output wire signed [47:0]   result_mant,
    output wire signed [15:0]   result_exp,
    output wire [31:0]          result_job,
    output wire [15:0]          result_channel,
    output wire                error_valid,
    output wire [7:0]           error_code,
    output wire                fault_lock
);

    /* 固定一拍缓存读端与局部计算连接。 */
    wire xr;
    wire wr;
    wire sr;
    wire [15:0] xi;
    wire [15:0] wi;
    wire [15:0] si;
    wire xv;
    wire wv;
    wire sv;
    wire [143:0] xd;
    wire [63:0] wd;
    wire [31:0] sd;
    wire [7:0] xe;
    wire [7:0] xm;
    wire [7:0] wm;
    wire storage_fault;

    xw_stage23_harness #(.DDR_MAX_BURST_BEATS(3)) storage (
        .clk(clk), .rst_n(rst_n), .job_valid(job_valid), .job_ready(job_ready),
        .job_id(job_id), .job_m(job_m), .job_n(job_n), .job_k(job_k), .job_m_tile(job_m_tile),
        .job_weight_base(job_weight_base), .job_scale_base(job_scale_base),
        .s_axis_tdata(s_axis_tdata), .s_axis_tvalid(s_axis_tvalid), .s_axis_tready(s_axis_tready),
        .s_axis_tkeep(s_axis_tkeep), .s_axis_tlast(s_axis_tlast), .s_axis_tuser(s_axis_tuser),
        .ddr_rd_req(ddr_rd_req), .ddr_rd_addra(ddr_rd_addra), .ddr_rd_addrb(ddr_rd_addrb),
        .ddr_rd_rdy(ddr_rd_rdy), .ddr_rd_data(ddr_rd_data), .ddr_rd_vld(ddr_rd_vld),
        .object_valid(object_valid), .object_ready(object_ready), .object_kind(object_kind),
        .object_index(object_index), .object_done(object_done), .x_loaded(x_loaded),
        .scale_loaded(s_loaded), .weight_loaded(w_loaded), .x_rd_req(xr), .x_rd_index(xi),
        .x_rd_valid(xv), .x_rd_data(xd), .x_rd_exp(xe), .x_rd_mask(xm),
        .weight_rd_req(wr), .weight_rd_index(wi), .weight_rd_valid(wv), .weight_rd_data(wd), .weight_rd_mask(wm),
        .scale_rd_req(sr), .scale_rd_index(si), .scale_rd_valid(sv), .scale_rd_bits(sd),
        .finish_test(1'b0), .result_ready(1'b0), .result_valid(), .result_code(), .fault_lock(storage_fault)
    );

    /* 测试层直接复用storage唯一公共复位释放；无生产层次依赖。 */
    xw_b3b_compute_ctrl core (
        .clk(clk), .rst_n(storage.local_rst_n), .abort(abort),
        .req_valid(compute_valid), .req_ready(compute_ready), .req_job(compute_job),
        .req_channel(compute_channel), .req_k(compute_k), .x_loaded(x_loaded), .w_loaded(w_loaded), .s_loaded(s_loaded),
        .upstream_fault(storage_fault), .upstream_code(storage.fatal_code), .slice_enable(slice_enable),
        .x_rd_req(xr), .x_rd_index(xi), .x_rd_valid(xv), .x_rd_data(xd), .x_rd_exp(xe), .x_rd_mask(xm),
        .w_rd_req(wr), .w_rd_index(wi), .w_rd_valid(wv), .w_rd_data(wd), .w_rd_mask(wm),
        .s_rd_req(sr), .s_rd_index(si), .s_rd_valid(sv), .s_rd_bits(sd),
        .result_valid(result_valid), .result_ready(result_ready), .result_mant(result_mant), .result_exp(result_exp),
        .result_job(result_job), .result_channel(result_channel), .error_valid(error_valid), .error_code(error_code), .fault_lock(fault_lock)
    );
endmodule
