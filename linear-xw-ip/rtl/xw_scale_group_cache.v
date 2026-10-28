// FP32 scale cache, group-aligned 512-bit DDR words.
// BFP N-group: 128 output channels, K block count ceil(K/128).
// One cached FP32 (32-bit) per K block; 16 scales per DDR word.
// Verilog-2001 only; RTL RAM style to be tuned after functional simulation.
module xw_scale_group_cache #(
    parameter integer MAX_K = 12288,
    parameter integer MAX_SCALE_WORDS = (MAX_K + 2047) / 2048
) (
    /*
     * =========================================================
     * 时钟与复位
     * =========================================================
     */
    input  wire                 clk,
    input  wire                 rst_n,

    /*
     * =========================================================
     * Scale 缓存装载接口
     * =========================================================
     */
    input  wire                 load_begin,
    input  wire [15:0]          load_words,
    input  wire [15:0]          load_scales,
    input  wire                 wr_valid,
    input  wire [511:0]         wr_data,
    input  wire [15:0]          wr_word_index,
    output reg                  loaded,
    output reg                  cache_error,

    /*
     * =========================================================
     * Scale 缓存读取接口
     * =========================================================
     */
    input  wire                 rd_req,
    input  wire [15:0]          rd_scale_index,
    output reg                  rd_valid,
    output reg  [31:0]          rd_scale_bits
);

    /*
     * =========================================================
     * FP32 Scale 数据缓存（每个 Word 包含 16 个 Scale）
     * =========================================================
     */
    reg [511:0] words [0:MAX_SCALE_WORDS-1];

    /*
     * =========================================================
     * 加载计数器与数量边界
     * =========================================================
     */
    reg [15:0] expected_words;
    reg [15:0] expected_scales;
    reg [15:0] words_written;

    /*
     * =========================================================
     * 读索引分解与 Word 选择
     * =========================================================
     */
    wire [15:0] rd_word_index;
    wire [3:0] rd_lane_index;
    wire [511:0] selected_word;


    /*
     * 将 Scale 索引分解为 512-bit Word 索引和 32-bit Lane 索引。
     */
    assign rd_word_index = rd_scale_index >> 4;
    assign rd_lane_index = rd_scale_index[3:0];
    assign selected_word = words[rd_word_index];

    /*
     * 缓存控制：load_begin 清除上轮状态，逐 Word 线性写入。
     * 根据 rd_req 读取 Scale，同步更新 rd_valid 与 cache_error。
     */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            loaded <= 1'b0;
            cache_error <= 1'b0;
            rd_valid <= 1'b0;
            rd_scale_bits <= 32'd0;
            expected_words <= 16'd0;
            expected_scales <= 16'd0;
            words_written <= 16'd0;
        end else begin
            rd_valid <= 1'b0;
            if (load_begin) begin
                loaded <= 1'b0;
                cache_error <= 1'b0;
                words_written <= 16'd0;
                expected_words <= load_words;
                expected_scales <= load_scales;
                if (load_words == 16'd0 ||
                    load_words > MAX_SCALE_WORDS ||
                    load_scales == 16'd0 ||
                    load_scales > MAX_SCALE_WORDS * 16 ||
                    load_words != ((load_scales + 16'd15) >> 4))
                    cache_error <= 1'b1;
            end else begin
                if (wr_valid) begin
                    if (loaded || cache_error ||
                        wr_word_index != words_written ||
                        wr_word_index >= expected_words)
                        cache_error <= 1'b1;
                    else begin
                        words[wr_word_index] <= wr_data;
                        words_written <= words_written + 16'd1;
                        if (words_written + 16'd1 == expected_words)
                            loaded <= 1'b1;
                    end
                end
                if (rd_req) begin
                    if (loaded && rd_scale_index < expected_scales) begin
                        rd_scale_bits <= selected_word >> (rd_lane_index * 32);
                        rd_valid <= 1'b1;
                    end else
                        cache_error <= 1'b1;
                end
            end
        end
    end
endmodule
