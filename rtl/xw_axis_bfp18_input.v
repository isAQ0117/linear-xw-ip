// Stage 2: M=1 BFP18/TUSER V2 parser, one element per unpack cycle.
// rst_n is the common asynchronously asserted, synchronously released reset.
module xw_axis_bfp18_input #(
    parameter integer MAX_K = 12288
)(
    input  wire         clk,
    input  wire         rst_n,
    input  wire         abort,
    input  wire         job_begin,
    input  wire  [31:0] job_id,
    input  wire  [15:0] job_k,
    input  wire [511:0] s_axis_tdata,
    input  wire         s_axis_tvalid,
    output wire         s_axis_tready,
    input  wire  [63:0] s_axis_tkeep,
    input  wire         s_axis_tlast,
    input  wire [127:0] s_axis_tuser,
    output reg          wr_valid,
    input  wire         wr_ready,
    output reg  [143:0] wr_data,
    output reg    [7:0] wr_mask,
    output reg    [7:0] wr_exp,
    output reg   [15:0] wr_word_index,
    output reg          wr_last,
    output reg          done,
    output reg          fault,
    output reg    [7:0] error_code
);

    // 参数、游标与单 Beat 暂存；pack 跨 Beat 保留。
    reg         active;
    reg  [31:0] active_id;
    reg  [15:0] active_k;
    reg   [8:0] group_id;
    reg   [7:0] group_offset;
    reg   [7:0] group_exp;
    reg         input_end;
    reg [511:0] beat_shift;
    reg   [5:0] remaining;
    reg   [7:0] beat_exp;
    reg         beat_final;
    reg [143:0] pack_data;
    reg   [2:0] pack_lanes;
    reg  [15:0] next_word;
    reg [143:0] packed_next;
    reg   [7:0] check_error;
    wire [16:0] group_start;
    wire [16:0] group_remaining;
    wire  [7:0] group_len;
    wire  [7:0] elements_left;
    wire  [5:0] beat_count;
    wire  [6:0] keep_bytes;
    wire [63:0] keep_expected;
    wire        group_last;
    wire        tensor_last;

    generate
        if (MAX_K < 1 || MAX_K > 65535) begin : g_invalid_parameters
            XW_INVALID_AXIS_INPUT_PARAMETERS u_must_fail_elaboration ();
        end
    endgenerate

    assign group_start = {1'b0, group_id, 7'd0};
    assign group_remaining = {1'b0, active_k} - group_start;
    assign group_len = group_remaining >= 17'd128 ? 8'd128 : group_remaining[7:0];
    assign elements_left = group_len - group_offset;
    assign beat_count = elements_left > 8'd28 ? 6'd28 : elements_left[5:0];
    assign keep_bytes = (beat_count * 18 + 7) / 8;
    assign keep_expected = 64'hffffffffffffffff >> (64 - keep_bytes);
    assign group_last = ({2'd0, beat_count} + group_offset == group_len);
    assign tensor_last = group_last && (group_start + {9'd0, group_len} == {1'b0, active_k});
    assign s_axis_tready = rst_n && !abort && !fault && !job_begin && active &&
                          !input_end && remaining == 0 && !wr_valid;

    // 冻结格式检查；只在 AXIS 握手沿使用结果。
    always @* begin
        check_error = 8'h00;
        if (s_axis_tuser[127:104] != 24'd0 ||
            s_axis_tuser[103:96] != 8'hb2 ||
            s_axis_tuser[95:89] != 7'd0 ||
            s_axis_tuser[63:57] != 7'd0 ||
            s_axis_tuser[31:0] != active_id)
            check_error = 8'h10;
        else if (s_axis_tuser[47:32] != 16'd0 ||
                 s_axis_tuser[56:48] != group_id ||
                 s_axis_tuser[79:72] != group_len ||
                 s_axis_tuser[87:80] != group_offset ||
                 (group_offset != 0 && s_axis_tuser[71:64] != group_exp))
            check_error = 8'h11;
        else if (s_axis_tkeep != keep_expected ||
                 (s_axis_tdata >> (beat_count * 18)) != 512'd0)
            check_error = 8'h12;
        else if (s_axis_tlast != group_last || s_axis_tuser[88] != tensor_last)
            check_error = 8'h13;
        packed_next = pack_data;
        packed_next[pack_lanes*18 +: 18] = beat_shift[17:0];
    end

    // 解包、8-lane 打包、输出保持与不可自动恢复的故障。
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active <= 1'b0;
            active_id <= 32'd0;
            active_k <= 16'd0;
            group_id <= 9'd0;
            group_offset <= 8'd0;
            group_exp <= 8'd0;
            input_end <= 1'b0;
            beat_shift <= 512'd0;
            remaining <= 6'd0;
            beat_exp <= 8'd0;
            beat_final <= 1'b0;
            pack_data <= 144'd0;
            pack_lanes <= 3'd0;
            next_word <= 16'd0;
            wr_valid <= 1'b0;
            wr_data <= 144'd0;
            wr_mask <= 8'd0;
            wr_exp <= 8'd0;
            wr_word_index <= 16'd0;
            wr_last <= 1'b0;
            done <= 1'b0;
            fault <= 1'b0;
            error_code <= 8'd0;
        end else begin
            done <= 1'b0;
            if (fault || abort) begin
                active <= 1'b0;
                wr_valid <= 1'b0;
                remaining <= 6'd0;
                if (!fault) begin
                    fault <= 1'b1;
                    error_code <= 8'h40;
                end
            end else if (job_begin && (active || wr_valid || job_k == 0 || job_k > MAX_K)) begin
                fault <= 1'b1;
                error_code <= 8'h40;
                wr_valid <= 1'b0;
                active <= 1'b0;
            end else if (job_begin) begin
                active <= 1'b1;
                active_id <= job_id;
                active_k <= job_k;
                group_id <= 9'd0;
                group_offset <= 8'd0;
                group_exp <= 8'd0;
                input_end <= 1'b0;
                remaining <= 6'd0;
                pack_data <= 144'd0;
                pack_lanes <= 3'd0;
                next_word <= 16'd0;
            end else if (s_axis_tvalid && s_axis_tready) begin
                if (check_error != 0) begin
                    fault <= 1'b1;
                    error_code <= check_error;
                    active <= 1'b0;
                    wr_valid <= 1'b0;
                    remaining <= 6'd0;
                end else begin
                    beat_shift <= s_axis_tdata;
                    remaining <= beat_count;
                    beat_exp <= s_axis_tuser[71:64];
                    beat_final <= tensor_last;
                    input_end <= tensor_last;
                    if (group_offset == 0)
                        group_exp <= s_axis_tuser[71:64];
                    if (group_last) begin
                        group_id <= group_id + 9'd1;
                        group_offset <= 8'd0;
                    end else begin
                        group_offset <= group_offset + {2'd0, beat_count};
                    end
                end
            end else if (wr_valid) begin
                if (wr_ready) begin
                    wr_valid <= 1'b0;
                    if (wr_last) begin
                        done <= 1'b1;
                        active <= 1'b0;
                    end
                end
            end else if (remaining != 0) begin
                beat_shift <= beat_shift >> 18;
                remaining <= remaining - 6'd1;
                if (pack_lanes == 3'd7 || (beat_final && remaining == 6'd1)) begin
                    wr_valid <= 1'b1;
                    wr_data <= packed_next;
                    wr_mask <= 8'hff >> (7 - pack_lanes);
                    wr_exp <= beat_exp;
                    wr_word_index <= next_word;
                    wr_last <= beat_final && remaining == 6'd1;
                    next_word <= next_word + 16'd1;
                    pack_data <= 144'd0;
                    pack_lanes <= 3'd0;
                end else begin
                    pack_data <= packed_next;
                    pack_lanes <= pack_lanes + 3'd1;
                end
            end
        end
    end
endmodule
