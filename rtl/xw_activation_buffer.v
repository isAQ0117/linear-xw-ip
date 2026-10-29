// Stage 2: complete M=1 X; 144-bit / 8-lane synchronous storage.
module xw_activation_buffer #(
    parameter integer MAX_K = 12288
)(
    input  wire         clk,
    input  wire         rst_n,
    input  wire         abort,
    input  wire         load_begin,
    input  wire  [15:0] load_k,
    input  wire         wr_valid,
    output wire         wr_ready,
    input  wire [143:0] wr_data,
    input  wire   [7:0] wr_mask,
    input  wire   [7:0] wr_exp,
    input  wire  [15:0] wr_word_index,
    input  wire         wr_last,
    output wire         loaded,
    output reg          fault,
    output reg    [7:0] error_code,
    input  wire         rd_req,
    input  wire  [15:0] rd_word_index,
    output wire         rd_valid,
    output wire [143:0] rd_data,
    output wire   [7:0] rd_exp,
    output reg    [7:0] rd_mask
);

    // RAM 不复位；仅有效标志和当前装载配置复位。
    localparam integer DEPTH = (MAX_K + 7) / 8;
    localparam integer GROUPS = (MAX_K + 127) / 128;
    reg [143:0] words [0:DEPTH-1];
    reg   [7:0] exponents [0:GROUPS-1];
    reg [143:0] ram_read_data;
    reg   [7:0] ram_read_exp;
    reg         read_seen;
    reg         loaded_reg;
    reg         read_valid_reg;
    reg         loading;
    reg  [15:0] active_k;
    reg  [15:0] total_words;
    reg  [15:0] written;
    reg   [7:0] current_exp;
    wire  [7:0] expected_mask;
    wire        final_word;
    wire  [7:0] read_mask;
    wire        control_conflict;
    wire        invalid_write;
    wire        write_enable;
    wire        read_enable;

    generate
        if (MAX_K < 1 || MAX_K > 65535) begin : g_invalid_parameters
            XW_INVALID_ACTIVATION_BUFFER_PARAMETERS u_must_fail_elaboration ();
        end
    endgenerate

    assign final_word = (written + 16'd1 == total_words);
    assign expected_mask = final_word && active_k[2:0] != 0 ?
                           (8'hff >> (8 - active_k[2:0])) : 8'hff;
    assign read_mask = rd_word_index + 16'd1 == total_words && active_k[2:0] != 0 ?
                       (8'hff >> (8 - active_k[2:0])) : 8'hff;
    assign wr_ready = rst_n && !abort && !fault && loading && !load_begin && !rd_req;
    assign loaded = rst_n && !abort && !fault && loaded_reg;
    assign rd_valid = rst_n && !abort && !fault && read_valid_reg;

    assign rd_data = read_seen ? ram_read_data : 144'd0;
    assign rd_exp = read_seen ? ram_read_exp : 8'd0;
    assign control_conflict = (load_begin && (loading || wr_valid || rd_req)) ||
                              (wr_valid && rd_req) ||
                              (load_begin && (load_k == 0 || load_k > MAX_K)) ||
                              (rd_req && (!loaded_reg || rd_word_index >= total_words));
    assign invalid_write = !loading || wr_word_index != written || written >= total_words ||
                           written >= DEPTH || wr_mask != expected_mask || wr_last != final_word ||
                           (written[3:0] != 0 && wr_exp != current_exp) ||
                           (final_word && active_k[2:0] != 0 &&
                            (wr_data >> (active_k[2:0]*18)) != 144'd0);
    assign write_enable = rst_n && !abort && !fault && !control_conflict &&
                          !load_begin && wr_valid && !invalid_write;
    assign read_enable = rst_n && !abort && !fault && !control_conflict &&
                         !load_begin && !wr_valid && rd_req;

    // RAM 独立无复位时序块，保证全宽同步读写而非阵列触发器。
    always @(posedge clk) begin
        if (write_enable) begin
            words[wr_word_index] <= wr_data;
            if (written[3:0] == 0)
                exponents[written >> 4] <= wr_exp;
        end
        if (read_enable) begin
            ram_read_data <= words[rd_word_index];
            ram_read_exp <= exponents[rd_word_index >> 4];
        end
    end

    // 单写口 / 同步读；读写冲突不依赖 RAM 的 read-during-write 模式。
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            loaded_reg <= 1'b0;
            read_valid_reg <= 1'b0;
            loading <= 1'b0;
            fault <= 1'b0;
            error_code <= 8'd0;
            active_k <= 16'd0;
            total_words <= 16'd0;
            written <= 16'd0;
            current_exp <= 8'd0;
            read_seen <= 1'b0;
            rd_mask <= 8'd0;
        end else begin
            read_valid_reg <= 1'b0;
            if (fault || abort) begin
                loaded_reg <= 1'b0;
                loading <= 1'b0;
                if (!fault) begin
                    fault <= 1'b1;
                    error_code <= 8'h40;
                end
            end else if (control_conflict) begin
                fault <= 1'b1;
                error_code <= 8'h40;
                loaded_reg <= 1'b0;
                loading <= 1'b0;
            end else if (load_begin) begin
                loaded_reg <= 1'b0;
                loading <= 1'b1;
                active_k <= load_k;
                total_words <= ({1'b0, load_k} + 17'd7) >> 3;
                written <= 16'd0;
            end else if (wr_valid) begin
                if (invalid_write) begin
                    fault <= 1'b1;
                    error_code <= 8'h40;
                    loaded_reg <= 1'b0;
                    loading <= 1'b0;
                end else begin
                    if (written[3:0] == 0) begin
                        current_exp <= wr_exp;
                    end
                    written <= written + 16'd1;
                    if (final_word) begin
                        loaded_reg <= 1'b1;
                        loading <= 1'b0;
                    end
                end
            end else if (rd_req) begin
                read_seen <= 1'b1;
                rd_mask <= read_mask;
                read_valid_reg <= 1'b1;
            end
        end
    end
endmodule
