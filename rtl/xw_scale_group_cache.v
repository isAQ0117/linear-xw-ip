// Linear xW: one complete N-group of raw FP32 Scale words.
// Stage 1 contract: XW-CONTRACT-STD-001 V1.0; Verilog-2001, ANSI ports.
// Each 512-bit DDR beat contains 16 little-endian FP32 bit patterns.
module xw_scale_group_cache #(
    parameter integer MAX_K           = 12288,
    parameter integer MAX_SCALE_WORDS = (MAX_K + 2047) / 2048
)(
    input  wire         clk,
    input  wire         rst_n,

    // 必须先锁存 load_begin，再接收第一拍 wr_valid。
    input  wire         load_begin,
    input  wire  [15:0] load_words,
    input  wire  [15:0] load_scales,
    input  wire         wr_valid,
    input  wire [511:0] wr_data,
    input  wire  [15:0] wr_word_index,
    output reg          loaded,
    output reg          cache_error,
    // 新增内部错误原因端口：写入错误 0x23，控制错误 0x40。
    output reg    [7:0] cache_error_code,

    input  wire         rd_req,
    input  wire  [15:0] rd_scale_index,
    output reg          rd_valid,
    output reg   [31:0] rd_scale_bits
);

    /*
     * =========================================================
     * Cache 参数容量检查（编译/展开时执行）。
     * =========================================================
     */
    localparam integer MAX_SCALES = (MAX_K + 127) / 128;
    localparam [7:0] ERR_DDR_BUFFER     = 8'h23;
    localparam [7:0] ERR_INTERNAL_FAULT = 8'h40;

    generate
        if ((MAX_K < 1 || MAX_K > 65535) ||
            (MAX_SCALE_WORDS < 1 || MAX_SCALE_WORDS > 65535) ||
            (MAX_SCALE_WORDS < (MAX_K + 2047) / 2048)) begin : g_invalid_parameters
            XW_INVALID_SCALE_CACHE_PARAMETERS u_must_fail_elaboration ();
        end
    endgenerate

    /*
     * =========================================================
     * 当前 Scale Group 的存储与索引计算。
     * =========================================================
     * RAM bits are intentionally NOT reset; loaded=0 invalidates them.
     */
    reg [511:0] words [0:MAX_SCALE_WORDS-1];
    reg  [15:0] expected_words;
    reg  [15:0] expected_scales;
    reg  [15:0] words_written;

    wire [15:0] rd_word_index;
    wire  [3:0] rd_lane_index;
    wire [16:0] words_needed;
    wire        load_parameters_valid;

    assign rd_word_index = rd_scale_index >> 4;
    assign rd_lane_index = rd_scale_index[3:0];
    assign words_needed  = ({1'b0, load_scales} + 17'd15) >> 4;
    assign load_parameters_valid =
        (load_words != 16'd0) &&
        (load_words <= MAX_SCALE_WORDS) &&
        (load_scales != 16'd0) &&
        (load_scales <= MAX_SCALES) &&
        ({1'b0, load_words} == words_needed);

    /*
     * =========================================================
     * Group 装载、同步读与严重故障锁定。
     * =========================================================
     * First fault wins.  A GOOD load_begin can invalidate a prior group;
     * it cannot clear cache_error or unlock a failed operation.
     * Error takes priority over read/write, including same-edge conflicts.
     */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            loaded           <= 1'b0;
            cache_error      <= 1'b0;
            cache_error_code <= 8'h00;
            rd_valid         <= 1'b0;
            rd_scale_bits    <= 32'd0;
            expected_words   <= 16'd0;
            expected_scales  <= 16'd0;
            words_written    <= 16'd0;
        end else begin
            rd_valid <= 1'b0;
            if (cache_error) begin
                // No further access; fault can only be cleared by reset.
                loaded <= 1'b0;
            end else if ((load_begin && (wr_valid || rd_req)) ||
                         (wr_valid && rd_req)) begin
                // No overlapping load/config/read/write transactions.
                loaded           <= 1'b0;
                cache_error      <= 1'b1;
                cache_error_code <= ERR_INTERNAL_FAULT;
                rd_scale_bits    <= 32'd0;
            end else if (load_begin) begin
                loaded          <= 1'b0;
                words_written   <= 16'd0;
                expected_words  <= load_words;
                expected_scales <= load_scales;
                if (!load_parameters_valid) begin
                    cache_error      <= 1'b1;
                    cache_error_code <= ERR_INTERNAL_FAULT;
                end
            end else if (wr_valid) begin
                if (loaded || wr_word_index != words_written ||
                    wr_word_index >= expected_words ||
                    wr_word_index >= MAX_SCALE_WORDS) begin
                    loaded           <= 1'b0;
                    cache_error      <= 1'b1;
                    cache_error_code <= ERR_DDR_BUFFER;
                    rd_scale_bits    <= 32'd0;
                end else begin
                    words[wr_word_index] <= wr_data;
                    words_written <= words_written + 16'd1;
                    if (words_written + 16'd1 == expected_words)
                        loaded <= 1'b1;
                end
            end else if (rd_req) begin
                if (loaded && rd_scale_index < expected_scales &&
                    rd_word_index < expected_words &&
                    rd_word_index < MAX_SCALE_WORDS) begin
                    rd_scale_bits <= words[rd_word_index] >> (rd_lane_index * 32);
                    rd_valid <= 1'b1;
                end else begin
                    loaded           <= 1'b0;
                    cache_error      <= 1'b1;
                    cache_error_code <= ERR_INTERNAL_FAULT;
                    rd_scale_bits    <= 32'd0;
                end
            end
        end
    end
endmodule
