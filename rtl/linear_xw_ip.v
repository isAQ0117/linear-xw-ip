`timescale 1ns / 1ps

/* 冻结35-port/10-parameter正式顶层；所有生产连接均为显式端口。 */
module linear_xw_ip #(
    parameter integer STATIC_DIM_MODE = 1,
    parameter integer N_DIM = 12288,
    parameter integer K_DIM = 4096,
    parameter integer MAX_N = 12288,
    parameter integer MAX_K = 12288,
    parameter integer MAX_M = 1,
    parameter integer MAX_M_TILE = 1,
    parameter integer P_N = 1,
    parameter integer P_K = 8,
    parameter integer AXIS_DATA_W = 512
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         job_valid,
    output wire         job_ready,
    input  wire [31:0]  job_id,
    input  wire [15:0]  job_m,
    input  wire [15:0]  job_n,
    input  wire [15:0]  job_k,
    input  wire [7:0]   job_m_tile,
    input  wire [28:0]  job_weight_base,
    input  wire [28:0]  job_scale_base,
    output wire         busy,
    output wire         status_valid,
    input  wire         status_ready,
    output wire [31:0]  status_job_id,
    output wire         status_ok,
    output wire [7:0]   status_error_code,
    input  wire [511:0] s_axis_tdata,
    input  wire         s_axis_tvalid,
    output wire         s_axis_tready,
    input  wire [63:0]  s_axis_tkeep,
    input  wire         s_axis_tlast,
    input  wire [127:0] s_axis_tuser,
    output wire [511:0] m_axis_tdata,
    output wire         m_axis_tvalid,
    input  wire         m_axis_tready,
    output wire [63:0]  m_axis_tkeep,
    output wire         m_axis_tlast,
    output wire [127:0] m_axis_tuser,
    output wire         ddr_rd_req,
    output wire [28:0]  ddr_rd_addra,
    output wire [28:0]  ddr_rd_addrb,
    input  wire         ddr_rd_rdy,
    input  wire [511:0] ddr_rd_data,
    input  wire         ddr_rd_vld
);
    /* 平台profile显式选择；仿真数值不作为硬件平台承诺。 */
`ifdef XW_SIM_DDR_BURST
    localparam integer DDR_BURST = `XW_SIM_DDR_BURST;
`else
`ifdef XW_PLATFORM_DDR_BURST
    localparam integer DDR_BURST = `XW_PLATFORM_DDR_BURST;
`else
    localparam integer DDR_BURST = 0;
`endif
`endif
    reg [1:0] system_release;
    reg [1:0] data_release;
    wire system_rst_n;
    wire data_rst_n;
    wire clear_datapath;
    wire cancel_datapath;
    wire fault_lock;
    wire [7:0] first_error;
    wire [31:0] active_id;
    wire [15:0] active_n;
    wire [15:0] active_k;
    wire [28:0] weight_base;
    wire [28:0] scale_base;
    wire [15:0] channel;
    wire [8:0] group_index;
    wire job_start;
    wire cfg_begin;
    wire cfg_done;
    wire cfg_error;
    wire [7:0] cfg_code;
    wire load_valid;
    wire load_ready;
    wire load_kind;
    wire [15:0] load_index;
    wire load_done;
    wire scale_begin;
    wire weight_begin;
    wire [15:0] load_words;
    wire [15:0] load_scales;
    wire [15:0] load_k;
    wire [15:0] segment_offset;
    wire cmd_valid;
    wire cmd_ready;
    wire [28:0] cmd_start;
    wire [28:0] cmd_end;
    wire [15:0] cmd_beats;
    wire cmd_kind;
    wire rx_busy;
    wire word_valid;
    wire [511:0] word_data;
    wire [15:0] word_index;
    wire word_kind;
    wire range_done;
    wire rx_fault;
    wire [7:0] rx_code;
    wire [15:0] logical_index;
    wire p_ready;
    wire p_done;
    wire p_fault;
    wire [7:0] p_code;
    wire x_wr_valid;
    wire x_wr_ready;
    wire [143:0] x_wr_data;
    wire [7:0] x_wr_mask;
    wire [7:0] x_wr_exp;
    wire [15:0] x_wr_index;
    wire x_wr_last;
    wire x_loaded;
    wire x_complete;
    wire x_fault;
    wire [7:0] x_code;
    wire w_loaded;
    wire w_fault;
    wire [7:0] w_code;
    wire s_loaded;
    wire s_fault;
    wire [7:0] s_code;
    wire a_fault;
    wire [7:0] a_code;
    wire x_rd_req;
    wire [15:0] x_rd_index;
    wire x_rd_valid;
    wire [143:0] x_rd_data;
    wire [7:0] x_rd_mask;
    wire [7:0] x_rd_exp;
    wire w_rd_req;
    wire [15:0] w_rd_index;
    wire w_rd_valid;
    wire [63:0] w_rd_data;
    wire [7:0] w_rd_mask;
    wire s_rd_req;
    wire [15:0] s_rd_index;
    wire s_rd_valid;
    wire [31:0] s_rd_bits;
    wire compute_valid;
    wire compute_ready;
    wire c_result_valid;
    wire c_result_ready;
    wire result_valid;
    wire result_ready;
    wire signed [47:0] result_mant;
    wire signed [15:0] result_exp;
    wire [31:0] result_job;
    wire [15:0] result_channel;
    wire c_fault;
    wire [7:0] c_code;
    wire c_lock;
    wire stage5_ready;
    wire group_done;
    wire [31:0] group_job;
    wire [8:0] committed_group;
    wire [7:0] group_len;
    wire signed [7:0] group_exp;
    wire job_results_ready;
    wire q_fault;
    wire [7:0] q_code;
    wire q_lock;
    wire rd_req;
    wire rd_ready;
    wire [15:0] rd_word_index;
    wire rd_valid;
    wire [143:0] rd_data;
    wire signed [7:0] rd_exp;
    wire [7:0] rd_mask;
    wire [15:0] rd_index;
    wire output_start;
    wire output_ready;
    wire output_done;
    wire output_fault;
    wire finish_valid;
    wire finish_ready;
    wire finish_ok;
    wire [7:0] finish_code;
    wire clean_boundary;
    wire stop_new;
    reg [7:0] raw_code;
    wire raw_fault;
    wire raw_system;
    reg [7:0] codes [0:7];
    integer source;

    generate
        if (MAX_M != 1 || MAX_M_TILE != 1 || P_N != 1 || P_K != 8 || AXIS_DATA_W != 512 || DDR_BURST < 1 || DDR_BURST > 65535) begin : g_invalid_parameters
            XW_INVALID_LINEAR_PLATFORM_PARAMETERS u_must_fail_elaboration ();
        end
`ifdef XW_SIM_DDR_BURST
`ifdef XW_PLATFORM_DDR_BURST
        XW_AMBIGUOUS_DDR_PLATFORM_PROFILE u_must_fail_elaboration ();
`endif
`endif
    endgenerate

    assign system_rst_n = system_release[1];
    assign data_rst_n = data_release[1];
    assign raw_fault = raw_code != 0;
    assign raw_system = raw_code < 8'h30 || raw_code == 8'h40;
    assign stop_new = cancel_datapath || raw_fault;
    assign clean_boundary = x_complete && !rx_busy && !word_valid && !cmd_valid;
    assign logical_index = segment_offset + word_index;
    assign s_axis_tready = p_ready && !stop_new && data_rst_n;
    assign result_valid = c_result_valid && !stop_new;
    assign c_result_ready = result_ready && !stop_new;

    /* 两个寄存释放链；局部reset仅Status接受后的CLEAN沿受控断言。 */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            system_release <= 0;
        else
            system_release <= {system_release[0], 1'b1};
    end

    /* Receiver/Status/Scheduler不受此局部清理影响。 */
    always @(posedge clk or negedge system_rst_n) begin
        if (!system_rst_n)
            data_release <= 0;
        else if (clear_datapath)
            data_release <= 0;
        else
            data_release <= {data_release[0], 1'b1};
    end

    /* 系统类优先，类内按冻结表顺序；取消后的派生40不覆盖根因。 */
    always @(*) begin
        codes[0] = p_fault ? p_code : 0;
        codes[1] = x_fault ? x_code : 0;
        codes[2] = w_fault ? w_code : 0;
        codes[3] = s_fault ? s_code : 0;
        codes[4] = a_fault ? a_code : 0;
        codes[5] = c_fault ? c_code : 0;
        codes[6] = q_fault ? q_code : 0;
        codes[7] = output_fault ? 8'h40 : 0;
        raw_code = rx_fault ? rx_code : 0;
        if (first_error == 0) begin
            for (source = 0; source < 8; source = source + 1) begin
                if (codes[source] != 0 &&
                    (raw_code == 0 ||
                     ((codes[source] < 8'h30 || codes[source] == 8'h40) && raw_code >= 8'h30 && raw_code != 8'h40) ||
                     (((codes[source] < 8'h30 || codes[source] == 8'h40) == (raw_code < 8'h30 || raw_code == 8'h40)) && codes[source] < raw_code)))
                    raw_code = codes[source];
            end
        end
    end

    xw_linear_scheduler #(.STATIC_DIM_MODE(STATIC_DIM_MODE), .N_DIM(N_DIM), .K_DIM(K_DIM), .MAX_N(MAX_N), .MAX_K(MAX_K)) scheduler (
        .clk(clk), .rst_n(system_rst_n), .job_valid(job_valid), .job_ready(job_ready), .job_id(job_id),
        .job_m(job_m), .job_n(job_n), .job_k(job_k), .job_m_tile(job_m_tile),
        .job_weight_base(job_weight_base), .job_scale_base(job_scale_base), .busy(busy),
        .active_id(active_id), .active_n(active_n), .active_k(active_k), .weight_base(weight_base), .scale_base(scale_base),
        .channel(channel), .group_index(group_index), .cfg_begin(cfg_begin), .cfg_done(cfg_done), .cfg_error(cfg_error), .cfg_error_code(cfg_code),
        .datapath_online(data_rst_n), .job_start(job_start), .stage5_ready(stage5_ready), .x_loaded(x_loaded), .input_done(p_done), .x_complete(x_complete),
        .load_valid(load_valid), .load_ready(load_ready), .load_kind(load_kind), .load_index(load_index), .load_done(load_done),
        .compute_valid(compute_valid), .compute_ready(compute_ready), .result_valid(result_valid), .result_ready(c_result_ready),
        .group_done(group_done), .committed_group(committed_group), .job_results_ready(job_results_ready),
        .output_start(output_start), .output_ready(output_ready), .output_done(output_done),
        .finish_valid(finish_valid), .finish_ready(finish_ready), .finish_ok(finish_ok), .finish_code(finish_code),
        .status_accept(status_valid && status_ready), .fault_valid(raw_fault), .fault_code(raw_code), .fault_system(raw_system),
        .clean_boundary(clean_boundary), .first_error(first_error), .fault_lock(fault_lock), .cancel_datapath(cancel_datapath), .clear_datapath(clear_datapath)
    );
    xw_ddr_addr_gen #(.MAX_N(MAX_N), .MAX_K(MAX_K), .DDR_MAX_BURST_BEATS(DDR_BURST)) address_generator (
        .clk(clk), .rst_n(data_rst_n), .abort(cancel_datapath), .cfg_begin(cfg_begin), .cfg_n(active_n), .cfg_k(active_k),
        .cfg_weight_base(weight_base), .cfg_scale_base(scale_base), .cfg_done(cfg_done), .cfg_error(cfg_error), .cfg_error_code(cfg_code),
        .load_valid(load_valid), .load_ready(load_ready), .load_kind(load_kind), .load_index(load_index),
        .scale_load_begin(scale_begin), .weight_load_begin(weight_begin), .load_words(load_words), .load_scales(load_scales), .load_k(load_k),
        .load_done(load_done), .cmd_valid(cmd_valid), .cmd_ready(cmd_ready), .cmd_addr_start(cmd_start), .cmd_addr_end(cmd_end),
        .cmd_beats(cmd_beats), .cmd_kind(cmd_kind), .range_done(range_done), .range_error(rx_fault), .range_error_code(rx_code),
        .buffer_loaded(cmd_kind ? w_loaded : s_loaded), .buffer_error(w_fault || s_fault), .buffer_error_code(w_fault ? w_code : s_code),
        .segment_offset(segment_offset), .fault(a_fault), .error_code(a_code)
    );
    xw_ddr_range_rx receiver (
        .clk(clk), .rst_n(system_rst_n), .cmd_valid(cmd_valid && !stop_new), .cmd_ready(cmd_ready),
        .cmd_addr_start(cmd_start), .cmd_addr_end(cmd_end), .cmd_beats(cmd_beats), .cmd_kind(cmd_kind),
        .ddr_rd_req(ddr_rd_req), .ddr_rd_addra(ddr_rd_addra), .ddr_rd_addrb(ddr_rd_addrb),
        .ddr_rd_rdy(ddr_rd_rdy), .ddr_rd_data(ddr_rd_data), .ddr_rd_vld(ddr_rd_vld),
        .busy(rx_busy), .word_valid(word_valid), .word_data(word_data), .word_index(word_index), .word_kind(word_kind),
        .range_done(range_done), .range_error(rx_fault), .range_error_code(rx_code)
    );
    xw_axis_bfp18_input #(.MAX_K(MAX_K)) input_parser (
        .clk(clk), .rst_n(data_rst_n), .abort(cancel_datapath), .job_begin(job_start), .job_id(active_id), .job_k(active_k),
        .s_axis_tdata(s_axis_tdata), .s_axis_tvalid(s_axis_tvalid && !stop_new), .s_axis_tready(p_ready),
        .s_axis_tkeep(s_axis_tkeep), .s_axis_tlast(s_axis_tlast), .s_axis_tuser(s_axis_tuser),
        .wr_valid(x_wr_valid), .wr_ready(x_wr_ready), .wr_data(x_wr_data), .wr_mask(x_wr_mask), .wr_exp(x_wr_exp),
        .wr_word_index(x_wr_index), .wr_last(x_wr_last), .done(p_done), .fault(p_fault), .error_code(p_code)
    );
    xw_activation_buffer #(.MAX_K(MAX_K)) activation (
        .clk(clk), .rst_n(data_rst_n), .abort(cancel_datapath), .load_begin(job_start), .load_k(active_k),
        .wr_valid(x_wr_valid && !stop_new), .wr_ready(x_wr_ready), .wr_data(x_wr_data), .wr_mask(x_wr_mask), .wr_exp(x_wr_exp),
        .wr_word_index(x_wr_index), .wr_last(x_wr_last), .loaded(x_loaded), .fault(x_fault), .error_code(x_code),
        .rd_req(x_rd_req), .rd_word_index(x_rd_index), .rd_valid(x_rd_valid), .rd_data(x_rd_data), .rd_exp(x_rd_exp), .rd_mask(x_rd_mask)
    );
    xw_weight_row_buffer #(.MAX_K(MAX_K)) weight_buffer (
        .clk(clk), .rst_n(data_rst_n), .abort(cancel_datapath), .load_begin(weight_begin), .load_k(load_k),
        .wr_valid(word_valid && word_kind && !stop_new), .wr_data(word_data), .wr_word_index(logical_index),
        .loaded(w_loaded), .fault(w_fault), .error_code(w_code), .rd_req(w_rd_req), .rd_word_index(w_rd_index),
        .rd_valid(w_rd_valid), .rd_data(w_rd_data), .rd_mask(w_rd_mask)
    );
    xw_scale_group_cache #(.MAX_K(MAX_K)) scale_cache (
        .clk(clk), .rst_n(data_rst_n), .load_begin(scale_begin), .load_words(load_words), .load_scales(load_scales),
        .wr_valid(word_valid && !word_kind && !stop_new), .wr_data(word_data), .wr_word_index(logical_index),
        .loaded(s_loaded), .cache_error(s_fault), .cache_error_code(s_code),
        .rd_req(s_rd_req), .rd_scale_index(s_rd_index), .rd_valid(s_rd_valid), .rd_scale_bits(s_rd_bits)
    );
    xw_b3b_compute_ctrl #(.MAX_K(MAX_K)) compute (
        .clk(clk), .rst_n(data_rst_n), .abort(cancel_datapath), .req_valid(compute_valid), .req_ready(compute_ready),
        .req_job(active_id), .req_channel(channel), .req_k(active_k), .x_loaded(x_loaded), .w_loaded(w_loaded), .s_loaded(s_loaded),
        .upstream_fault(1'b0), .upstream_code(8'd0), .slice_enable(1'b1),
        .x_rd_req(x_rd_req), .x_rd_index(x_rd_index), .x_rd_valid(x_rd_valid), .x_rd_data(x_rd_data), .x_rd_exp(x_rd_exp), .x_rd_mask(x_rd_mask),
        .w_rd_req(w_rd_req), .w_rd_index(w_rd_index), .w_rd_valid(w_rd_valid), .w_rd_data(w_rd_data), .w_rd_mask(w_rd_mask),
        .s_rd_req(s_rd_req), .s_rd_index(s_rd_index), .s_rd_valid(s_rd_valid), .s_rd_bits(s_rd_bits),
        .result_valid(c_result_valid), .result_ready(c_result_ready), .result_mant(result_mant), .result_exp(result_exp),
        .result_job(result_job), .result_channel(result_channel), .error_valid(c_fault), .error_code(c_code), .fault_lock(c_lock)
    );
    xw_stage5_ctrl #(.MAX_N(MAX_N)) stage5 (
        .clk(clk), .rst_n(data_rst_n), .abort(1'b0), .job_start(job_start), .job_ready(stage5_ready), .job_id(active_id), .job_n(active_n),
        .retire(1'b0), .clean_boundary(clean_boundary), .upstream_fault(cancel_datapath), .upstream_code(first_error), .upstream_lock(fault_lock),
        .result_valid(result_valid), .result_ready(result_ready), .result_mant(result_mant), .result_exp(result_exp), .result_job(result_job), .result_channel(result_channel),
        .group_done(group_done), .group_job(group_job), .group_id(committed_group), .group_len(group_len), .group_exp(group_exp),
        .job_results_ready(job_results_ready), .error_valid(q_fault), .error_code(q_code), .fault_lock(q_lock),
        .rd_req(rd_req), .rd_ready(rd_ready), .rd_word_index(rd_word_index), .rd_valid(rd_valid), .rd_data(rd_data), .rd_exp(rd_exp), .rd_mask(rd_mask), .rd_index(rd_index)
    );
    xw_axis_bfp18_output #(.MAX_N(MAX_N)) output_sender (
        .clk(clk), .rst_n(data_rst_n), .start(output_start), .start_ready(output_ready), .job_id(active_id), .job_n(active_n),
        .halt(stop_new), .output_done(output_done), .fault(output_fault), .rd_ready(rd_ready), .rd_req(rd_req), .rd_word_index(rd_word_index),
        .rd_valid(rd_valid), .rd_data(rd_data), .rd_exp(rd_exp), .rd_mask(rd_mask), .rd_index(rd_index),
        .m_axis_tdata(m_axis_tdata), .m_axis_tvalid(m_axis_tvalid), .m_axis_tready(m_axis_tready),
        .m_axis_tkeep(m_axis_tkeep), .m_axis_tlast(m_axis_tlast), .m_axis_tuser(m_axis_tuser)
    );
    xw_job_status status_slot (
        .clk(clk), .rst_n(system_rst_n), .finish_valid(finish_valid), .finish_ready(finish_ready),
        .finish_job_id(active_id), .finish_ok(finish_ok), .finish_error_code(finish_code),
        .status_valid(status_valid), .status_ready(status_ready), .status_job_id(status_job_id), .status_ok(status_ok), .status_error_code(status_error_code)
    );
endmodule
