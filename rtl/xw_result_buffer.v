`timescale 1ns / 1ps

/* 完整Job结果；顺序提交前缀授权，不清RAM，不泄漏旧Job尾部。 */
module xw_result_buffer #(
    parameter integer MAX_N = 12288
) (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                cancel,
    input  wire                job_begin,
    input  wire [15:0]          job_n,
    input  wire                attempt_begin,
    input  wire [8:0]           group_index,
    input  wire [7:0]           group_len,
    input  wire                q_valid,
    input  wire [6:0]           q_index,
    input  wire signed [17:0]   q_mant,
    input  wire                q_last,
    input  wire                commit,
    input  wire signed [7:0]    commit_exp,
    input  wire                publish,
    output reg                 group_committed,
    output wire                job_results_ready,
    input  wire                rd_req,
    output wire                rd_ready,
    input  wire [15:0]          rd_word_index,
    output wire                rd_valid,
    output wire [143:0]         rd_data,
    output wire signed [7:0]    rd_exp,
    output reg [7:0]           rd_mask,
    output reg [15:0]          rd_index,
    output reg                 fault
);
    /* 全宽同步RAM与提交计数；容量按参数配置。 */
    localparam integer WORDS = (MAX_N + 7) / 8;
    localparam integer GROUPS = (MAX_N + 127) / 128;
    reg [143:0] words [0:WORDS-1];
    reg [7:0] exponents [0:GROUPS-1];
    reg [143:0] ram_data;
    reg [7:0] ram_exp;
    reg read_pending;
    reg read_seen;
    reg active;
    reg visible;
    reg [15:0] active_n;
    reg [15:0] total_words;
    reg [9:0] total_groups;
    reg [9:0] committed_count;
    reg attempt_active;
    reg [8:0] current_group;
    reg [7:0] length;
    reg [7:0] received;
    reg attempt_range_bad;
    reg [143:0] pack_data;
    reg [143:0] assembled;
    wire [16:0] group_remaining;
    wire [7:0] expected_length;
    wire [15:0] write_index;
    wire flush_word;
    wire bad;
    wire enable;
    wire write_enable;
    wire commit_enable;
    wire read_enable;
    integer lane;

    generate
        if (MAX_N < 1 || MAX_N > 65535) begin : g_invalid_parameters
            XW_INVALID_RESULT_BUFFER_PARAMETERS u_must_fail_elaboration ();
        end
    endgenerate

    assign group_remaining = {1'b0, active_n} - {1'b0, group_index, 7'd0};
    assign expected_length = group_remaining >= 128 ? 8'd128 : group_remaining[7:0];
    assign write_index = {3'd0, current_group, 4'd0} + {12'd0, q_index[6:3]};
    assign flush_word = q_index[2:0] == 7 || q_last;
    assign enable = rst_n && !cancel && !fault;
    assign bad = (job_begin && (active || attempt_begin || q_valid || commit || publish ||
                  job_n == 0 || job_n > MAX_N)) ||
                 (attempt_begin && (!active || visible || q_valid || commit || publish ||
                  {1'b0, group_index} != committed_count || committed_count >= total_groups ||
                  group_len != expected_length || group_len == 0 || group_len > 128 ||
                  (attempt_active && received != length))) ||
                 (q_valid && (!attempt_active || visible || commit || publish ||
                  received >= length || {1'b0, q_index} != received ||
                  q_last != (received + 8'd1 == length) || write_index >= WORDS)) ||
                 (commit && (!attempt_active || visible || received != length || q_valid ||
                  pack_data != 0 || attempt_range_bad || publish || {1'b0, current_group} != committed_count)) ||
                 (publish && (!active || visible || attempt_active || committed_count != total_groups)) ||
                 (visible && rd_req && rd_word_index >= total_words);
    assign write_enable = enable && !bad && !job_begin && q_valid && flush_word;
    assign commit_enable = enable && !bad && !job_begin && commit;
    assign job_results_ready = enable && visible;
    assign rd_ready = job_results_ready && rd_word_index < total_words;
    assign read_enable = rd_req && rd_ready && !bad && !job_begin;
    assign rd_valid = enable && visible && read_pending;
    assign rd_data = job_results_ready && read_seen ? ram_data : 144'd0;
    assign rd_exp = job_results_ready && read_seen ? ram_exp : 8'd0;

    /* lane0开始清空pack；尾word高lane绝不复用旧RAM数据。 */
    always @(*) begin
        assembled = q_index[2:0] == 0 ? 144'd0 : pack_data;
        for (lane = 0; lane < 8; lane = lane + 1) begin
            if (q_index[2:0] == lane)
                assembled[lane*18 +: 18] = q_mant;
        end
    end

    /* RAM不带复位，Mantissa和指数均为同步一拍读。 */
    always @(posedge clk) begin
        if (write_enable)
            words[write_index] <= assembled;
        if (commit_enable)
            exponents[current_group] <= commit_exp;
        if (read_enable) begin
            ram_data <= words[rd_word_index];
            ram_exp <= exponents[rd_word_index >> 4];
        end
    end

    /* 元数据与提交互斥；失败清有效前缀而非遍历RAM。 */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active <= 0;
            visible <= 0;
            active_n <= 0;
            total_words <= 0;
            total_groups <= 0;
            committed_count <= 0;
            attempt_active <= 0;
            current_group <= 0;
            length <= 0;
            received <= 0;
            attempt_range_bad <= 0;
            pack_data <= 0;
            group_committed <= 0;
            read_pending <= 0;
            read_seen <= 0;
            rd_mask <= 0;
            rd_index <= 0;
            fault <= 0;
        end else if (cancel) begin
            active <= 0;
            visible <= 0;
            committed_count <= 0;
            attempt_active <= 0;
            received <= 0;
            attempt_range_bad <= 0;
            pack_data <= 0;
            group_committed <= 0;
            read_pending <= 0;
            read_seen <= 0;
            rd_mask <= 0;
            fault <= 0;
        end else if (fault || bad) begin
            fault <= 1;
            visible <= 0;
            active <= 0;
            attempt_active <= 0;
            group_committed <= 0;
            read_pending <= 0;
        end else begin
            group_committed <= 0;
            read_pending <= read_enable;
            if (read_enable) begin
                read_seen <= 1;
                rd_index <= rd_word_index;
                rd_mask <= rd_word_index + 16'd1 == total_words && active_n[2:0] != 0 ?
                           (8'hff >> (8 - active_n[2:0])) : 8'hff;
            end
            if (job_begin) begin
                active <= 1;
                visible <= 0;
                active_n <= job_n;
                total_words <= ({1'b0, job_n} + 17'd7) >> 3;
                total_groups <= ({1'b0, job_n} + 17'd127) >> 7;
                committed_count <= 0;
                attempt_active <= 0;
                pack_data <= 0;
                read_seen <= 0;
            end else if (attempt_begin) begin
                attempt_active <= 1;
                current_group <= group_index;
                length <= group_len;
                received <= 0;
                attempt_range_bad <= 0;
                pack_data <= 0;
            end else if (q_valid) begin
                received <= received + 1'b1;
                if (q_mant == -18'sd131072)
                    attempt_range_bad <= 1;
                pack_data <= flush_word ? 144'd0 : assembled;
            end else if (commit) begin
                committed_count <= committed_count + 1'b1;
                attempt_active <= 0;
                group_committed <= 1;
            end else if (publish) begin
                visible <= 1;
            end
        end
    end
endmodule
