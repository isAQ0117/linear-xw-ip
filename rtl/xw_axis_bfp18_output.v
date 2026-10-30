`timescale 1ns / 1ps

/* 8→28装配；无反压同步RAM的4-word容量预留与独立AXIS输出槽。 */
module xw_axis_bfp18_output #(
    parameter integer MAX_N = 12288
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         start,
    output wire         start_ready,
    input  wire [31:0]  job_id,
    input  wire [15:0]  job_n,
    input  wire         halt,
    output reg          output_done,
    output reg          fault,
    input  wire         rd_ready,
    output wire         rd_req,
    output wire [15:0]  rd_word_index,
    input  wire         rd_valid,
    input  wire [143:0] rd_data,
    input  wire [7:0]   rd_exp,
    input  wire [7:0]   rd_mask,
    input  wire [15:0]  rd_index,
    output reg [511:0] m_axis_tdata,
    output reg          m_axis_tvalid,
    input  wire         m_axis_tready,
    output reg [63:0]  m_axis_tkeep,
    output reg          m_axis_tlast,
    output reg [127:0] m_axis_tuser
);
    /* FIFO数据不复位，仅清指针、count、pending及所有权。 */
    reg [151:0] fifo [0:3];
    reg [1:0] wp;
    reg [1:0] rp;
    reg [2:0] count;
    reg pending;
    reg [15:0] issued;
    reg [15:0] received;
    reg [15:0] words;
    reg active;
    reg [31:0] active_id;
    reg [15:0] active_n;
    reg [8:0] group_id;
    reg [7:0] offset;
    reg [5:0] packed;
    reg [511:0] assembly;
    reg half_word;
    reg [7:0] exponent;
    reg [7:0] response_exp;
    reg [511:0] assembled;
    reg [143:0] masked_head;
    wire [143:0] head;
    wire [7:0] head_exp;
    wire [16:0] remaining;
    wire [7:0] length;
    wire [5:0] beat_lanes;
    wire [3:0] head_lanes;
    wire [3:0] take;
    wire [6:0] keep_bytes;
    wire consume;
    wire pop;
    wire push;
    wire flush;
    wire group_last;
    wire tensor_last;
    wire [7:0] expected_mask;
    wire bad;
    integer lane;

    generate
        if (MAX_N < 1 || MAX_N > 65535) begin : g_invalid_parameters
            XW_INVALID_AXIS_OUTPUT_PARAMETERS u_must_fail_elaboration ();
        end
    endgenerate

    assign start_ready = rst_n && !active && !m_axis_tvalid && !fault && !halt;
    assign rd_req = rst_n && active && !halt && !fault && issued < words &&
                    ({1'b0, count} + pending < 4);
    assign rd_word_index = issued;
    assign remaining = {1'b0, active_n} - {1'b0, group_id, 7'd0};
    assign length = remaining >= 128 ? 8'd128 : remaining[7:0];
    assign beat_lanes = length - offset > 28 ? 6'd28 : length - offset;
    assign head_lanes = remaining - {9'd0, offset} - packed >= (half_word ? 4 : 8) ?
                        (half_word ? 4'd4 : 4'd8) :
                        (remaining - {9'd0, offset} - packed);
    assign take = beat_lanes - packed < head_lanes ? beat_lanes - packed : head_lanes;
    assign consume = rst_n && active && !halt && !fault && count != 0 &&
                     (!m_axis_tvalid || m_axis_tready);
    assign pop = consume && (take == head_lanes);
    assign push = rd_valid && active && !halt && !fault;
    assign flush = consume && packed + take == beat_lanes;
    assign group_last = offset + beat_lanes == length;
    assign tensor_last = group_last && remaining <= 128;
    assign keep_bytes = (beat_lanes * 18 + 7) >> 3;
    assign {head_exp, head} = fifo[rp];
    assign expected_mask = received + 1'b1 == words && active_n[2:0] != 0 ?
                           (8'hff >> (8 - active_n[2:0])) : 8'hff;
    assign bad = (start && (!start_ready || job_n == 0 || job_n > MAX_N)) ||
                 (active && !halt && (rd_valid != pending || count > 4 ||
                  (pending && count == 4) ||
                  (rd_valid && (rd_index != received || rd_mask != expected_mask ||
                   (received + 1'b1 == words && active_n[2:0] != 0 &&
                    (rd_data >> (active_n[2:0]*18)) != 0) ||
                   (received[3:0] != 0 && rd_exp != response_exp))) ||
                  (consume && (take == 0 || (offset != 0 || packed != 0) && head_exp != exponent))));

    /* 只选择0/72bit半word；插入位置是七个静态接线，padding恒0。 */
    always @(*) begin
        masked_head = half_word ? {72'd0, head[143:72]} : head;
        for (lane = 0; lane < 8; lane = lane + 1) begin
            if (lane >= take)
                masked_head[lane*18 +: 18] = 0;
        end
        assembled = assembly;
        case (packed)
            0: assembled[143:0] = masked_head;
            4: assembled[215:72] = masked_head;
            8: assembled[287:144] = masked_head;
            12: assembled[359:216] = masked_head;
            16: assembled[431:288] = masked_head;
            20: assembled[503:360] = masked_head;
            24: assembled[503:432] = masked_head[71:0];
            default: assembled = assembly;
        endcase
    end

    /* 返回必有预留空间；halt后在途数据被作废，不改已宣告beat。 */
    always @(posedge clk) begin
        if (push && !bad)
            fifo[wp] <= {rd_exp, rd_data};
    end

    /* 输出槽仅空闲或真实握手时可改写，done严格晚于最终握手。 */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wp <= 0;
            rp <= 0;
            count <= 0;
            pending <= 0;
            issued <= 0;
            received <= 0;
            words <= 0;
            active <= 0;
            active_id <= 0;
            active_n <= 0;
            group_id <= 0;
            offset <= 0;
            packed <= 0;
            assembly <= 0;
            half_word <= 0;
            exponent <= 0;
            response_exp <= 0;
            output_done <= 0;
            fault <= 0;
            m_axis_tdata <= 0;
            m_axis_tvalid <= 0;
            m_axis_tkeep <= 0;
            m_axis_tlast <= 0;
            m_axis_tuser <= 0;
        end else begin
            output_done <= 0;
            if (m_axis_tvalid && m_axis_tready) begin
                m_axis_tvalid <= 0;
                if (m_axis_tuser[88] && !halt && !fault && !bad) begin
                    output_done <= 1;
                    active <= 0;
                end
            end
            if (bad)
                fault <= 1;
            if (halt || fault || bad) begin
                active <= 0;
                pending <= 0;
                count <= 0;
            end else if (start && start_ready) begin
                active <= 1;
                active_id <= job_id;
                active_n <= job_n;
                words <= ({1'b0, job_n} + 17'd7) >> 3;
                wp <= 0;
                rp <= 0;
                count <= 0;
                pending <= 0;
                issued <= 0;
                received <= 0;
                group_id <= 0;
                offset <= 0;
                packed <= 0;
                assembly <= 0;
                half_word <= 0;
                exponent <= 0;
                response_exp <= 0;
            end else if (active) begin
                pending <= rd_req && rd_ready;
                if (rd_req && rd_ready)
                    issued <= issued + 1'b1;
                if (push) begin
                    wp <= wp + 1'b1;
                    received <= received + 1'b1;
                    response_exp <= rd_exp;
                end
                if (pop) begin
                    rp <= rp + 1'b1;
                    half_word <= 0;
                end else if (consume) begin
                    half_word <= 1;
                end
                case ({push, pop})
                    2'b10: count <= count + 1'b1;
                    2'b01: count <= count - 1'b1;
                    default: count <= count;
                endcase
                if (consume) begin
                    exponent <= head_exp;
                    if (flush) begin
                        m_axis_tvalid <= 1;
                        m_axis_tdata <= assembled;
                        m_axis_tkeep <= 64'hffffffffffffffff >> (64 - keep_bytes);
                        m_axis_tlast <= group_last;
                        m_axis_tuser <= {24'd0, 8'hb2, 7'd0, tensor_last, offset,
                                         length, head_exp, 7'd0, group_id, 16'd0, active_id};
                        packed <= 0;
                        assembly <= 0;
                        if (group_last) begin
                            offset <= 0;
                            group_id <= group_id + 1'b1;
                        end else begin
                            offset <= offset + beat_lanes;
                        end
                    end else begin
                        packed <= packed + take;
                        assembly <= assembled;
                    end
                end
            end
        end
    end
endmodule
