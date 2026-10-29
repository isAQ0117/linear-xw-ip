// TEST ONLY: input preflight + storage wiring, no compute/output/scheduler.
module xw_stage23_harness #(
    parameter integer STATIC_DIM_MODE = 0,
    parameter integer N_DIM = 2,
    parameter integer K_DIM = 129,
    parameter integer MAX_N = 129,
    parameter integer MAX_K = 12288,
    parameter integer DDR_MAX_BURST_BEATS = 0
)(
    input  wire         clk,
    input  wire         rst_n,
    input  wire         job_valid,
    output wire         job_ready,
    input  wire  [31:0] job_id,
    input  wire  [15:0] job_m,
    input  wire  [15:0] job_n,
    input  wire  [15:0] job_k,
    input  wire   [7:0] job_m_tile,
    input  wire  [28:0] job_weight_base,
    input  wire  [28:0] job_scale_base,
    input  wire [511:0] s_axis_tdata,
    input  wire         s_axis_tvalid,
    output wire         s_axis_tready,
    input  wire  [63:0] s_axis_tkeep,
    input  wire         s_axis_tlast,
    input  wire [127:0] s_axis_tuser,
    output wire         ddr_rd_req,
    output wire  [28:0] ddr_rd_addra,
    output wire  [28:0] ddr_rd_addrb,
    input  wire         ddr_rd_rdy,
    input  wire [511:0] ddr_rd_data,
    input  wire         ddr_rd_vld,
    input  wire         object_valid,
    output wire         object_ready,
    input  wire         object_kind,
    input  wire  [15:0] object_index,
    output wire         object_done,
    output wire         x_loaded,
    output wire         scale_loaded,
    output wire         weight_loaded,
    input  wire         x_rd_req,
    input  wire  [15:0] x_rd_index,
    output wire         x_rd_valid,
    output wire [143:0] x_rd_data,
    output wire   [7:0] x_rd_exp,
    output wire   [7:0] x_rd_mask,
    input  wire         scale_rd_req,
    input  wire  [15:0] scale_rd_index,
    output wire         scale_rd_valid,
    output wire  [31:0] scale_rd_bits,
    input  wire         weight_rd_req,
    input  wire  [15:0] weight_rd_index,
    output wire         weight_rd_valid,
    output wire  [63:0] weight_rd_data,
    output wire   [7:0] weight_rd_mask,
    input  wire         finish_test,
    output reg          result_valid,
    input  wire         result_ready,
    output reg    [7:0] result_code,
    output wire         fault_lock
);

    // 全域唯一复位释放同步器，所有数据管线使用同一个 local_rst_n。
    reg   [1:0] reset_release;
    wire        local_rst_n;
    localparam [3:0] S_IDLE = 4'd0, S_DIMS = 4'd1, S_CFG = 4'd2,
                     S_CHECK = 4'd3, S_XBEGIN = 4'd4, S_X = 4'd5,
                     S_ACCESS = 4'd6, S_RESULT = 4'd7, S_LOCK = 4'd8;
    reg   [3:0] state;
    reg  [31:0] active_id;
    reg  [15:0] active_m;
    reg   [7:0] active_tile;
    reg  [28:0] weight_base;
    reg  [28:0] scale_base;
    reg         locked;
    reg   [7:0] first_code;
    reg         scale_owned;
    reg         weight_owned;
    wire        job_accept;
    wire        dims_valid, dims_error;
    wire [15:0] active_n, active_k;
    wire        cfg_done, cfg_error;
    wire  [7:0] cfg_code;
    wire        ag_ready, ag_done;
    wire        scale_begin, weight_begin;
    wire [15:0] load_words, load_scales, load_k;
    wire        cmd_valid, cmd_ready, cmd_kind;
    wire [28:0] cmd_start, cmd_end;
    wire [15:0] cmd_beats, offset;
    wire        rx_busy, word_valid, word_kind, range_done, rx_error;
    wire [511:0] word_data;
    wire [15:0] word_index;
    wire [16:0] logical_index;
    wire  [7:0] rx_code;
    wire        p_valid, p_ready, p_last, p_done, p_fault;
    wire [143:0] p_data;
    wire  [7:0] p_mask, p_exp, p_code;
    wire [15:0] p_index;
    wire        x_raw_loaded, x_fault, w_raw_loaded, w_fault, s_raw_loaded, s_fault, ag_fault;
    wire  [7:0] x_code, w_code, s_code, ag_code;
    wire        s_raw_rd_valid;
    wire        fatal;
    reg   [7:0] fatal_code;
    wire        allow_access;
    wire        parser_axis_ready;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            reset_release <= 2'b00;
        else
            reset_release <= {reset_release[0], 1'b1};
    end
    assign local_rst_n = reset_release[1];
    assign fatal = locked || p_fault || x_fault || w_fault || s_fault || ag_fault || rx_error;
    assign fault_lock = fatal;
    assign allow_access = state == S_ACCESS && !fatal;
    assign job_ready = local_rst_n && state == S_IDLE && !fatal;
    assign job_accept = job_valid && job_ready;
    assign s_axis_tready = parser_axis_ready && state == S_X && !fatal;
    assign object_ready = allow_access && ag_ready;
    assign object_done = ag_done && !fatal;
    assign x_loaded = x_raw_loaded && (state == S_X || state == S_ACCESS) && !fatal;
    assign scale_loaded = s_raw_loaded && scale_owned && allow_access;
    assign weight_loaded = w_raw_loaded && weight_owned && allow_access;
    assign scale_rd_valid = s_raw_rd_valid && scale_owned && allow_access;
    assign logical_index = {1'b0, offset} + {1'b0, word_index};

    // 同沿首错按冻结错误表顺序选择；广播 abort 后的次生40不覆盖首错。
    always @* begin
        fatal_code = 8'h40;
        if (p_fault && p_code < fatal_code) fatal_code = p_code;
        if (rx_error && rx_code < fatal_code) fatal_code = rx_code;
        if (ag_fault && ag_code < fatal_code) fatal_code = ag_code;
        if (s_fault && s_code < fatal_code) fatal_code = s_code;
        if (w_fault && w_code < fatal_code) fatal_code = w_code;
        if (x_fault && x_code < fatal_code) fatal_code = x_code;
    end

    xw_job_dim_cfg #(.STATIC_DIM_MODE(STATIC_DIM_MODE), .N_DIM(N_DIM), .K_DIM(K_DIM),
        .MAX_N(MAX_N), .MAX_K(MAX_K)) dims (
        .clk(clk), .rst_n(local_rst_n), .job_accept(job_accept), .job_n(job_n), .job_k(job_k),
        .cfg_valid(dims_valid), .cfg_error(dims_error), .active_n(active_n), .active_k(active_k),
        .n_groups(), .k_blocks(), .weight_words_per_row(), .scale_words_per_group()
    );
    xw_axis_bfp18_input #(.MAX_K(MAX_K)) parser (
        .clk(clk), .rst_n(local_rst_n), .abort(fatal), .job_begin(state == S_XBEGIN && !fatal),
        .job_id(active_id), .job_k(active_k), .s_axis_tdata(s_axis_tdata),
        .s_axis_tvalid(s_axis_tvalid && state == S_X && !fatal), .s_axis_tready(parser_axis_ready),
        .s_axis_tkeep(s_axis_tkeep), .s_axis_tlast(s_axis_tlast), .s_axis_tuser(s_axis_tuser),
        .wr_valid(p_valid), .wr_ready(p_ready), .wr_data(p_data), .wr_mask(p_mask), .wr_exp(p_exp),
        .wr_word_index(p_index), .wr_last(p_last), .done(p_done), .fault(p_fault), .error_code(p_code)
    );
    xw_activation_buffer #(.MAX_K(MAX_K)) activation (
        .clk(clk), .rst_n(local_rst_n), .abort(fatal), .load_begin(state == S_XBEGIN && !fatal),
        .load_k(active_k), .wr_valid(p_valid && !fatal), .wr_ready(p_ready), .wr_data(p_data),
        .wr_mask(p_mask), .wr_exp(p_exp), .wr_word_index(p_index), .wr_last(p_last),
        .loaded(x_raw_loaded), .fault(x_fault), .error_code(x_code),
        .rd_req(x_rd_req && allow_access), .rd_word_index(x_rd_index), .rd_valid(x_rd_valid),
        .rd_data(x_rd_data), .rd_exp(x_rd_exp), .rd_mask(x_rd_mask)
    );
    xw_ddr_addr_gen #(.MAX_N(MAX_N), .MAX_K(MAX_K), .DDR_MAX_BURST_BEATS(DDR_MAX_BURST_BEATS)) address_gen (
        .clk(clk), .rst_n(local_rst_n), .abort(fatal), .cfg_begin(state == S_CFG && !fatal),
        .cfg_n(active_n), .cfg_k(active_k), .cfg_weight_base(weight_base), .cfg_scale_base(scale_base),
        .cfg_done(cfg_done), .cfg_error(cfg_error), .cfg_error_code(cfg_code),
        .load_valid(object_valid && allow_access), .load_ready(ag_ready),
        .load_kind(object_kind), .load_index(object_index), .scale_load_begin(scale_begin),
        .weight_load_begin(weight_begin), .load_words(load_words), .load_scales(load_scales),
        .load_k(load_k), .load_done(ag_done), .cmd_valid(cmd_valid), .cmd_ready(cmd_ready),
        .cmd_addr_start(cmd_start), .cmd_addr_end(cmd_end), .cmd_beats(cmd_beats), .cmd_kind(cmd_kind),
        .range_done(range_done), .range_error(rx_error), .range_error_code(rx_code),
        .buffer_loaded(cmd_kind ? w_raw_loaded : s_raw_loaded),
        .buffer_error(w_fault || s_fault), .buffer_error_code(w_fault ? w_code : s_code),
        .segment_offset(offset), .fault(ag_fault), .error_code(ag_code)
    );
    xw_ddr_range_rx receiver (
        .clk(clk), .rst_n(local_rst_n), .cmd_valid(cmd_valid), .cmd_ready(cmd_ready),
        .cmd_addr_start(cmd_start), .cmd_addr_end(cmd_end), .cmd_beats(cmd_beats), .cmd_kind(cmd_kind),
        .ddr_rd_req(ddr_rd_req), .ddr_rd_addra(ddr_rd_addra), .ddr_rd_addrb(ddr_rd_addrb),
        .ddr_rd_rdy(ddr_rd_rdy), .ddr_rd_data(ddr_rd_data), .ddr_rd_vld(ddr_rd_vld),
        .busy(rx_busy), .word_valid(word_valid), .word_data(word_data), .word_index(word_index),
        .word_kind(word_kind), .range_done(range_done), .range_error(rx_error), .range_error_code(rx_code)
    );
    xw_scale_group_cache #(.MAX_K(MAX_K)) scales (
        .clk(clk), .rst_n(local_rst_n), .load_begin(scale_begin), .load_words(load_words),
        .load_scales(load_scales), .wr_valid(word_valid && !word_kind && !fatal),
        .wr_data(word_data), .wr_word_index(logical_index[15:0]), .loaded(s_raw_loaded),
        .cache_error(s_fault), .cache_error_code(s_code), .rd_req(scale_rd_req && allow_access && scale_owned),
        .rd_scale_index(scale_rd_index), .rd_valid(s_raw_rd_valid), .rd_scale_bits(scale_rd_bits)
    );
    xw_weight_row_buffer #(.MAX_K(MAX_K)) weights (
        .clk(clk), .rst_n(local_rst_n), .abort(fatal), .load_begin(weight_begin), .load_k(load_k),
        .wr_valid(word_valid && word_kind && !fatal), .wr_data(word_data), .wr_word_index(logical_index[15:0]),
        .loaded(w_raw_loaded), .fault(w_fault), .error_code(w_code),
        .rd_req(weight_rd_req && allow_access), .rd_word_index(weight_rd_index), .rd_valid(weight_rd_valid),
        .rd_data(weight_rd_data), .rd_mask(weight_rd_mask)
    );

    // 测试控制状态；地址检查完成前绝不开放 AXIS 输入。
    always @(posedge clk or negedge local_rst_n) begin
        if (!local_rst_n) begin
            state <= S_IDLE;
            active_id <= 32'd0;
            active_m <= 16'd0;
            active_tile <= 8'd0;
            weight_base <= 29'd0;
            scale_base <= 29'd0;
            locked <= 1'b0;
            first_code <= 8'd0;
            result_valid <= 1'b0;
            result_code <= 8'd0;
            scale_owned <= 1'b0;
            weight_owned <= 1'b0;
        end else begin
            if (scale_begin) scale_owned <= 1'b1;
            if (weight_begin) weight_owned <= 1'b1;
            if (fatal && !locked) begin
                locked <= 1'b1;
                first_code <= fatal_code;
                scale_owned <= 1'b0;
                weight_owned <= 1'b0;
                if (state != S_IDLE && state != S_LOCK) begin
                    if (!result_valid) begin
                        result_valid <= 1'b1;
                        result_code <= fatal_code;
                    end
                    state <= S_RESULT;
                end else begin
                    state <= S_LOCK;
                end
            end else begin
                case (state)
                    S_IDLE: begin
                        if (job_accept) begin
                            active_id <= job_id;
                            active_m <= job_m;
                            active_tile <= job_m_tile;
                            weight_base <= job_weight_base;
                            scale_base <= job_scale_base;
                            scale_owned <= 1'b0;
                            weight_owned <= 1'b0;
                            state <= S_DIMS;
                        end
                    end
                    S_DIMS: begin
                        if (dims_valid) begin
                            if (dims_error || active_m != 1 || active_tile != 1) begin
                                result_valid <= 1'b1;
                                result_code <= dims_error ? 8'h01 : 8'h02;
                                state <= S_RESULT;
                            end else state <= S_CFG;
                        end
                    end
                    S_CFG: state <= S_CHECK;
                    S_CHECK: begin
                        if (cfg_done) begin
                            if (cfg_error) begin
                                result_valid <= 1'b1;
                                result_code <= cfg_code;
                                state <= S_RESULT;
                            end else state <= S_XBEGIN;
                        end
                    end
                    S_XBEGIN: state <= S_X;
                    S_X: begin
                        if (x_raw_loaded && p_done) state <= S_ACCESS;
                    end
                    S_ACCESS: begin
                        if (finish_test && ag_ready && !object_valid && !rx_busy) begin
                            result_valid <= 1'b1;
                            result_code <= 8'h00;
                            state <= S_RESULT;
                        end
                    end
                    S_RESULT: begin
                        if (result_valid && result_ready) begin
                            result_valid <= 1'b0;
                            state <= locked ? S_LOCK : S_IDLE;
                        end
                    end
                    S_LOCK: state <= S_LOCK;
                    default: begin
                        locked <= 1'b1;
                        first_code <= 8'h40;
                        state <= S_LOCK;
                    end
                endcase
            end
        end
    end
endmodule
