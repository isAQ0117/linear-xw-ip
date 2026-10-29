// Stage 3: raw FP8 complete row, 512-bit DDR write / 8-byte B1 read.
module xw_weight_row_buffer #(
    parameter integer MAX_K = 12288
)(
    input  wire         clk,
    input  wire         rst_n,
    input  wire         abort,
    input  wire         load_begin,
    input  wire  [15:0] load_k,
    input  wire         wr_valid,
    input  wire [511:0] wr_data,
    input  wire  [15:0] wr_word_index,
    output wire         loaded,
    output reg          fault,
    output reg    [7:0] error_code,
    input  wire         rd_req,
    input  wire  [15:0] rd_word_index,
    output wire         rd_valid,
    output wire  [63:0] rd_data,
    output reg    [7:0] rd_mask
);

    // 单拍全宽写入，容量覆盖连续且无 Ready 的所有 DDR 返回。
    localparam integer DEPTH = (MAX_K + 63) / 64;
    reg [511:0] words [0:DEPTH-1];
    reg [511:0] ram_read_word;
    reg   [2:0] read_lane;
    reg         read_seen;
    reg         loading;
    reg         loaded_reg;
    reg         read_valid_reg;
    reg  [15:0] active_k;
    reg  [15:0] total_words;
    reg  [15:0] read_words;
    reg  [15:0] written;
    wire  [7:0] read_mask;
    wire [63:0] selected_bytes;
    wire        control_conflict;
    wire        invalid_write;
    wire        write_enable;
    wire        read_enable;
    genvar lane;

    generate
        if (MAX_K < 1 || MAX_K > 65535) begin : g_invalid_parameters
            XW_INVALID_WEIGHT_BUFFER_PARAMETERS u_must_fail_elaboration ();
        end
    endgenerate

    assign loaded = rst_n && !abort && !fault && loaded_reg;
    assign rd_valid = rst_n && !abort && !fault && read_valid_reg;
    assign read_mask = rd_word_index + 16'd1 == read_words && active_k[2:0] != 0 ?
                       (8'hff >> (8 - active_k[2:0])) : 8'hff;
    assign selected_bytes = ram_read_word >> (read_lane * 64);
    generate
        for (lane = 0; lane < 8; lane = lane + 1) begin : g_read_lane_mask
            assign rd_data[lane*8 +: 8] = read_seen && rd_mask[lane] ? selected_bytes[lane*8 +: 8] : 8'd0;
        end
    endgenerate
    assign control_conflict = (load_begin && (loading || wr_valid || rd_req)) ||
                              (wr_valid && rd_req) ||
                              (load_begin && (load_k == 0 || load_k > MAX_K)) ||
                              (rd_req && (!loaded_reg || rd_word_index >= read_words));
    assign invalid_write = !loading || wr_word_index != written || written >= total_words || written >= DEPTH;
    assign write_enable = rst_n && !abort && !fault && !control_conflict &&
                          !load_begin && wr_valid && !invalid_write;
    assign read_enable = rst_n && !abort && !fault && !control_conflict &&
                         !load_begin && !wr_valid && rd_req;

    // 原生512bit同步RAM读后选择8-byte，lane与mask同沿寄存。
    always @(posedge clk) begin
        if (write_enable)
            words[wr_word_index] <= wr_data;
        if (read_enable)
            ram_read_word <= words[rd_word_index >> 3];
    end

    // 有效位复位，RAM 无全阵列清零；读写并发定义为内部错误。
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            loading <= 1'b0;
            loaded_reg <= 1'b0;
            read_valid_reg <= 1'b0;
            fault <= 1'b0;
            error_code <= 8'd0;
            active_k <= 16'd0;
            total_words <= 16'd0;
            read_words <= 16'd0;
            written <= 16'd0;
            read_seen <= 1'b0;
            read_lane <= 3'd0;
            rd_mask <= 8'd0;
        end else begin
            read_valid_reg <= 1'b0;
            if (fault || abort) begin
                loading <= 1'b0;
                loaded_reg <= 1'b0;
                if (!fault) begin
                    fault <= 1'b1;
                    error_code <= 8'h40;
                end
            end else if (control_conflict) begin
                fault <= 1'b1;
                error_code <= 8'h40;
                loading <= 1'b0;
                loaded_reg <= 1'b0;
            end else if (load_begin) begin
                loading <= 1'b1;
                loaded_reg <= 1'b0;
                active_k <= load_k;
                total_words <= ({1'b0, load_k} + 17'd63) >> 6;
                read_words <= ({1'b0, load_k} + 17'd7) >> 3;
                written <= 16'd0;
            end else if (wr_valid) begin
                if (invalid_write) begin
                    fault <= 1'b1;
                    error_code <= 8'h23;
                    loading <= 1'b0;
                    loaded_reg <= 1'b0;
                end else begin
                    written <= written + 16'd1;
                    if (written + 16'd1 == total_words) begin
                        loading <= 1'b0;
                        loaded_reg <= 1'b1;
                    end
                end
            end else if (rd_req) begin
                read_seen <= 1'b1;
                read_lane <= rd_word_index[2:0];
                rd_mask <= read_mask;
                read_valid_reg <= 1'b1;
            end
        end
    end
endmodule
