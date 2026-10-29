// Stage 3: Layout V3 validation and one logical Group/Row -> physical ranges.
// DDR_MAX_BURST_BEATS=0 deliberately requires explicit platform selection.
module xw_ddr_addr_gen #(
    parameter integer MAX_N = 12288,
    parameter integer MAX_K = 12288,
    parameter integer DDR_MAX_BURST_BEATS = 0
)(
    input  wire         clk,
    input  wire         rst_n,
    input  wire         abort,
    input  wire         cfg_begin,
    input  wire  [15:0] cfg_n,
    input  wire  [15:0] cfg_k,
    input  wire  [28:0] cfg_weight_base,
    input  wire  [28:0] cfg_scale_base,
    output reg          cfg_done,
    output reg          cfg_error,
    output reg    [7:0] cfg_error_code,
    input  wire         load_valid,
    output wire         load_ready,
    input  wire         load_kind,
    input  wire  [15:0] load_index,
    output wire         scale_load_begin,
    output wire         weight_load_begin,
    output wire  [15:0] load_words,
    output wire  [15:0] load_scales,
    output wire  [15:0] load_k,
    output wire         load_done,
    output wire         cmd_valid,
    input  wire         cmd_ready,
    output wire  [28:0] cmd_addr_start,
    output wire  [28:0] cmd_addr_end,
    output wire  [15:0] cmd_beats,
    output wire         cmd_kind,
    input  wire         range_done,
    input  wire         range_error,
    input  wire   [7:0] range_error_code,
    input  wire         buffer_loaded,
    input  wire         buffer_error,
    input  wire   [7:0] buffer_error_code,
    output wire  [15:0] segment_offset,
    output reg          fault,
    output reg    [7:0] error_code
);

    // 配置以64bit计算完整独占边界，不允许29bit截断后再校验。
    localparam [2:0] S_IDLE = 3'd0, S_INIT = 3'd1, S_REQUEST = 3'd2,
                     S_RECEIVE = 3'd3, S_COMMIT = 3'd4, S_LOADED = 3'd5;
    reg         load_done_reg;
    reg   [2:0] state;
    reg         configured;
    reg  [15:0] active_n;
    reg  [15:0] active_k;
    reg  [28:0] weight_base;
    reg  [28:0] scale_base;
    reg  [15:0] weight_words;
    reg  [15:0] scale_words;
    reg  [15:0] n_groups;
    reg  [15:0] k_blocks;
    reg         kind;
    reg  [28:0] object_base;
    reg  [15:0] total_words;
    reg  [15:0] offset;
    wire [63:0] cfg_rw;
    wire [63:0] cfg_rs;
    wire [63:0] cfg_groups;
    wire [63:0] cfg_wend;
    wire [63:0] cfg_send;
    wire [63:0] index_base;
    wire [63:0] segment_start;
    wire [63:0] segment_end;
    wire [15:0] remaining_words;
    wire        blocked;

    generate
        if (MAX_N < 1 || MAX_N > 65535 || MAX_K < 1 || MAX_K > 65535 ||
            DDR_MAX_BURST_BEATS < 1 || DDR_MAX_BURST_BEATS > 65535) begin : g_invalid_parameters
            XW_INVALID_ADDR_GEN_PARAMETERS u_must_fail_elaboration ();
        end
    endgenerate

    assign cfg_rw = ({48'd0, cfg_k} + 64'd63) >> 6;
    assign cfg_rs = ({48'd0, cfg_k} + 64'd2047) >> 11;
    assign cfg_groups = ({48'd0, cfg_n} + 64'd127) >> 7;
    assign cfg_wend = {35'd0, cfg_weight_base} + 64'd8 * {48'd0, cfg_n} * cfg_rw;
    assign cfg_send = {35'd0, cfg_scale_base} + 64'd8 * cfg_groups * cfg_rs;
    assign index_base = load_kind ?
        {35'd0, weight_base} + 64'd8 * {48'd0, load_index} * {48'd0, weight_words} :
        {35'd0, scale_base} + 64'd8 * {48'd0, load_index} * {48'd0, scale_words};
    assign remaining_words = total_words - offset;
    assign cmd_beats = remaining_words > DDR_MAX_BURST_BEATS ? DDR_MAX_BURST_BEATS : remaining_words;
    assign segment_start = {35'd0, object_base} + 64'd8 * {48'd0, offset};
    assign segment_end = segment_start + 64'd8 * ({48'd0, cmd_beats} - 64'd1);
    assign blocked = !rst_n || abort || fault || range_error || buffer_error;
    // 同沿Receiver故障可在NBA后出现，公开完成必须立即屏蔽。
    assign load_done = load_done_reg && !blocked;
    assign load_ready = !blocked && configured && state == S_IDLE && !cfg_begin;
    assign scale_load_begin = !blocked && state == S_INIT && !kind;
    assign weight_load_begin = !blocked && state == S_INIT && kind;
    assign load_words = total_words;
    assign load_scales = k_blocks;
    assign load_k = active_k;
    assign cmd_valid = !blocked && state == S_REQUEST &&
                       cmd_beats != 0 && segment_end < 64'd536870912;
    assign cmd_addr_start = segment_start[28:0];
    assign cmd_addr_end = segment_end[28:0];
    assign cmd_kind = kind;
    assign segment_offset = offset;

    // INIT仅初始化一次；COMMIT保护最后寄存Beat的逻辑写地址。
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            configured <= 1'b0;
            active_n <= 16'd0;
            active_k <= 16'd0;
            weight_base <= 29'd0;
            scale_base <= 29'd0;
            weight_words <= 16'd0;
            scale_words <= 16'd0;
            n_groups <= 16'd0;
            k_blocks <= 16'd0;
            kind <= 1'b0;
            object_base <= 29'd0;
            total_words <= 16'd0;
            offset <= 16'd0;
            cfg_done <= 1'b0;
            cfg_error <= 1'b0;
            cfg_error_code <= 8'd0;
            load_done_reg <= 1'b0;
            fault <= 1'b0;
            error_code <= 8'd0;
        end else begin
            cfg_done <= 1'b0;
            load_done_reg <= 1'b0;
            if (fault) begin
                configured <= 1'b0;
            end else if (range_error || buffer_error || abort) begin
                fault <= 1'b1;
                error_code <= range_error ? range_error_code :
                              (buffer_error ? buffer_error_code : 8'h40);
                configured <= 1'b0;
            end else if (cfg_begin && (state != S_IDLE || load_valid)) begin
                fault <= 1'b1;
                error_code <= 8'h40;
                configured <= 1'b0;
            end else if (cfg_begin) begin
                cfg_done <= 1'b1;
                cfg_error <= 1'b0;
                cfg_error_code <= 8'd0;
                configured <= 1'b0;
                if (cfg_n == 0 || cfg_k == 0 || cfg_n > MAX_N || cfg_k > MAX_K) begin
                    cfg_error <= 1'b1;
                    cfg_error_code <= 8'h01;
                end else if (cfg_weight_base[2:0] != 0 || cfg_scale_base[2:0] != 0 ||
                             cfg_wend > 64'd536870912 || cfg_send > 64'd536870912 ||
                             !(cfg_wend <= {35'd0, cfg_scale_base} ||
                               cfg_send <= {35'd0, cfg_weight_base})) begin
                    cfg_error <= 1'b1;
                    cfg_error_code <= 8'h03;
                end else begin
                    configured <= 1'b1;
                    active_n <= cfg_n;
                    active_k <= cfg_k;
                    weight_base <= cfg_weight_base;
                    scale_base <= cfg_scale_base;
                    weight_words <= cfg_rw[15:0];
                    scale_words <= cfg_rs[15:0];
                    n_groups <= cfg_groups[15:0];
                    k_blocks <= ({1'b0, cfg_k} + 17'd127) >> 7;
                end
            end else begin
                case (state)
                    S_IDLE: begin
                        if (load_valid && load_ready) begin
                            if ((load_kind && load_index >= active_n) ||
                                (!load_kind && load_index >= n_groups) ||
                                index_base >= 64'd536870912) begin
                                fault <= 1'b1;
                                error_code <= 8'h40;
                            end else begin
                                kind <= load_kind;
                                object_base <= index_base[28:0];
                                total_words <= load_kind ? weight_words : scale_words;
                                offset <= 16'd0;
                                state <= S_INIT;
                            end
                        end
                    end
                    S_INIT: state <= S_REQUEST;
                    S_REQUEST: begin
                        if (cmd_beats == 0 || segment_end >= 64'd536870912) begin
                            fault <= 1'b1;
                            error_code <= 8'h20;
                        end else if (cmd_ready) begin
                            state <= S_RECEIVE;
                        end
                    end
                    S_RECEIVE: begin
                        if (range_done)
                            state <= S_COMMIT;
                    end
                    S_COMMIT: begin
                        if (offset + cmd_beats == total_words) begin
                            state <= S_LOADED;
                        end else begin
                            offset <= offset + cmd_beats;
                            state <= S_REQUEST;
                        end
                    end
                    S_LOADED: begin
                        if (buffer_loaded) begin
                            load_done_reg <= 1'b1;
                            state <= S_IDLE;
                        end
                    end
                    default: begin
                        fault <= 1'b1;
                        error_code <= 8'h40;
                    end
                endcase
            end
        end
    end
endmodule
