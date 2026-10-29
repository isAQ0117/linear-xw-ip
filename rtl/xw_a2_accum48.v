`timescale 1ns / 1ps

/* 有序每Block RNE；快速signed128路径，特殊64bit分段精确加减。 */
module xw_a2_accum48 (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                abort,
    input  wire                clear,
    input  wire                in_valid,
    output wire                in_ready,
    input  wire signed [71:0]   in_mant,
    input  wire signed [11:0]   in_exp,
    input  wire [15:0]          in_block,
    output wire                busy,
    output wire                update_valid,
    output reg signed [47:0]   state_mant,
    output reg signed [15:0]   state_exp,
    output reg [15:0]          out_block,
    output reg                 special_path,
    output reg                 fault,
    output reg [7:0]           error_code
);

    /* FSM与精确指数；17bit覆盖全部输入字段差值和输出范围检查。 */
    localparam [3:0] S_IDLE = 0, S_ALIGN = 1, S_SUM = 2, S_ABS = 3,
                     S_LEAD = 4, S_ROUND = 5, S_CHECK = 6, S_COMMIT = 7,
                     S_SETUP = 8, S_CHUNK = 9, S_ZERO = 10;
    reg [3:0] state;
    reg update_pending;
    reg signed [47:0] old_mant;
    reg signed [71:0] term_mant;
    reg signed [16:0] target_exp;
    reg [16:0] old_shift;
    reg [16:0] term_shift;
    reg signed [127:0] aligned_old;
    reg signed [127:0] aligned_term;
    reg signed [127:0] exact_sum;
    reg [127:0] window;
    reg signed [16:0] window_base;
    reg [16:0] magnitude_length;
    reg negative;
    reg is_power_two;
    reg sticky;
    reg [16:0] norm_shift;
    reg [7:0] round_shift;
    reg [48:0] rounded;
    reg retried;

    /* 特殊路径：恒定存储，按64bit从低到高传播carry/borrow。 */
    reg [71:0] high_mag;
    reg [71:0] low_mag;
    reg high_negative;
    reg low_negative;
    reg [16:0] gap;
    reg signed [16:0] high_offset;
    reg subtract_mode;
    reg high_larger;
    reg carry_borrow;
    reg [9:0] chunk_index;
    reg [9:0] chunk_count;
    reg [63:0] previous_chunk;
    reg low_sticky;
    wire signed [16:0] state_exp_wide;
    wire signed [16:0] term_exp_wide;
    wire signed [16:0] difference;
    wire [16:0] absolute_gap;
    wire [16:0] high_length;
    wire [16:0] low_length;
    wire larger_compare;
    wire signed [16:0] chunk_position;
    wire signed [16:0] high_position;
    wire [63:0] high_chunk;
    wire [63:0] low_chunk;
    wire [63:0] first_chunk;
    wire [63:0] second_chunk;
    wire [64:0] chunk_arithmetic;
    wire [63:0] chunk_result;
    wire [16:0] selected_length;
    wire selected_power;
    wire [16:0] initial_shift;
    wire signed [16:0] relative_shift;
    wire signed [16:0] result_exponent;

    /* 二分优先编码，避免线性128级逐位优先链。 */
    function [7:0] bit_length;
        input [127:0] value;
        reg [127:0] v;
        reg [7:0] n;
        begin
            v = value;
            n = 0;
            if (v[127:64] != 0) begin v = v >> 64; n = n + 64; end
            if (v[63:32] != 0) begin v = v >> 32; n = n + 32; end
            if (v[31:16] != 0) begin v = v >> 16; n = n + 16; end
            if (v[15:8] != 0) begin v = v >> 8; n = n + 8; end
            if (v[7:4] != 0) begin v = v >> 4; n = n + 4; end
            if (v[3:2] != 0) begin v = v >> 2; n = n + 2; end
            if (v[1] != 0) begin v = v >> 1; n = n + 1; end
            bit_length = value == 0 ? 8'd0 : n + 1'b1;
        end
    endfunction

    /* 分字节单1检测，避免128bit减一后再接归一化优先树的长carry路径。 */
    function single_bit;
        input [127:0] value;
        reg [15:0] nonzero_bytes;
        reg all_single;
        reg [7:0] part;
        integer k;
        begin
            nonzero_bytes = 0;
            all_single = 1;
            for (k = 0; k < 16; k = k + 1) begin
                part = value[k*8 +: 8];
                nonzero_bytes[k] = part != 0;
                if ((part & (part - 8'd1)) != 0)
                    all_single = 0;
            end
            single_bit = all_single && nonzero_bytes != 0 &&
                         (nonzero_bytes & (nonzero_bytes - 16'd1)) == 0;
        end
    endfunction

    /* 仅从72bit源提取一个chunk；指数gap不改变组合运算宽度。 */
    function [63:0] extract_chunk;
        input [71:0] value;
        input signed [16:0] position;
        reg [5:0] left_amount;
        begin
            left_amount = 6'd0 - position[5:0];
            if (position >= 17'sd72 || position <= -17'sd64)
                extract_chunk = 64'd0;
            else if (position >= 0)
                extract_chunk = value >> position[6:0];
            else
                extract_chunk = value << left_amount;
        end
    endfunction

    /* 对完整精确结果的有效窗口RNE，sticky是加减完成后所有低段的OR。 */
    function [48:0] round_window;
        input [127:0] value;
        input [7:0] amount;
        input low_nonzero;
        reg [48:0] q;
        reg [127:0] mask;
        reg tail;
        begin
            q = value >> amount;
            mask = 128'd0;
            tail = low_nonzero;
            if (amount != 0) begin
                mask = (128'd1 << (amount - 1'b1)) - 1'b1;
                tail = tail || ((value & mask) != 0);
                if (value[amount-1'b1] && (tail || q[0]))
                    q = q + 1'b1;
            end
            round_window = q;
        end
    endfunction

    assign in_ready = rst_n && !abort && !fault && !clear && state == S_IDLE;
    assign busy = state != S_IDLE;
    assign update_valid = rst_n && !abort && !fault && update_pending;
    assign state_exp_wide = {state_exp[15], state_exp};
    assign term_exp_wide = {{5{in_exp[11]}}, in_exp};
    assign difference = state_exp_wide - term_exp_wide;
    assign absolute_gap = difference < 0 ? -difference : difference;
    assign high_length = {9'd0, bit_length({56'd0, high_mag})} + gap;
    assign low_length = {9'd0, bit_length({56'd0, low_mag})};
    /* 仅等位长时移位比较，此时总长≤72；不截断潜在143bit值。 */
    assign larger_compare = high_length > low_length ||
                            (high_length == low_length && (high_mag << gap) >= low_mag);
    assign chunk_position = $signed({1'b0, chunk_index, 6'd0});
    assign high_position = high_offset;
    assign high_chunk = extract_chunk(high_mag, high_position);
    assign low_chunk = extract_chunk(low_mag, chunk_position);
    assign first_chunk = high_larger ? high_chunk : low_chunk;
    assign second_chunk = high_larger ? low_chunk : high_chunk;
    assign chunk_arithmetic = subtract_mode ?
        ({1'b0, first_chunk} - {1'b0, second_chunk} - {64'd0, carry_borrow}) :
        ({1'b0, high_chunk} + {1'b0, low_chunk} + {64'd0, carry_borrow});
    assign chunk_result = chunk_arithmetic[63:0];
    assign selected_length = special_path ? magnitude_length : {9'd0, bit_length(window)};
    assign selected_power = special_path ? is_power_two :
                            single_bit(window);
    assign initial_shift = selected_length > ((negative && selected_power) ? 17'd48 : 17'd47) ?
                           selected_length - ((negative && selected_power) ? 17'd48 : 17'd47) : 17'd0;
    assign relative_shift = $signed(initial_shift) - window_base;
    assign result_exponent = target_exp + $signed(norm_shift);

    /* 状态提交仅发生于S_COMMIT/S_ZERO；错误不覆盖旧pair。 */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            update_pending <= 0;
            state_mant <= 0;
            state_exp <= 0;
            out_block <= 0;
            special_path <= 0;
            fault <= 0;
            error_code <= 0;
            old_mant <= 0;
            term_mant <= 0;
            target_exp <= 0;
            old_shift <= 0;
            term_shift <= 0;
            aligned_old <= 0;
            aligned_term <= 0;
            exact_sum <= 0;
            window <= 0;
            window_base <= 0;
            magnitude_length <= 0;
            negative <= 0;
            is_power_two <= 0;
            sticky <= 0;
            norm_shift <= 0;
            round_shift <= 0;
            rounded <= 0;
            retried <= 0;
            high_mag <= 0;
            low_mag <= 0;
            high_negative <= 0;
            low_negative <= 0;
            gap <= 0;
            high_offset <= 0;
            subtract_mode <= 0;
            high_larger <= 0;
            carry_borrow <= 0;
            chunk_index <= 0;
            chunk_count <= 0;
            previous_chunk <= 0;
            low_sticky <= 0;
        end else begin
            update_pending <= 0;
            if (fault || abort || (clear && state != S_IDLE)) begin
                state <= S_IDLE;
                if (!fault) begin
                    fault <= 1;
                    error_code <= 8'h40;
                end
            end else if (clear) begin
                state_mant <= 0;
                state_exp <= 0;
            end else begin
                case (state)
                    S_IDLE: begin
                        if (in_valid && in_ready) begin
                            old_mant <= state_mant;
                            term_mant <= in_mant;
                            out_block <= in_block;
                            retried <= 0;
                            window <= 0;
                            window_base <= 0;
                            sticky <= 0;
                            magnitude_length <= 0;
                            is_power_two <= 0;
                            target_exp <= state_mant == 0 ? term_exp_wide :
                                          (difference < 0 ? state_exp_wide : term_exp_wide);
                            old_shift <= state_mant == 0 || difference < 0 ? 17'd0 : absolute_gap;
                            term_shift <= state_mant == 0 || difference >= 0 ? 17'd0 : absolute_gap;
                            special_path <= state_mant != 0 && in_mant != 0 && absolute_gap > 48;
                            if (in_mant == 0) begin
                                state <= S_ZERO;
                            end else if (state_mant == 0 || absolute_gap <= 48) begin
                                state <= S_ALIGN;
                            end else begin
                                gap <= absolute_gap;
                                if (difference >= 0) begin
                                    high_mag <= state_mant[47] ? -$signed({{24{state_mant[47]}}, state_mant}) : {{24{state_mant[47]}}, state_mant};
                                    low_mag <= in_mant[71] ? -in_mant : in_mant;
                                    high_negative <= state_mant[47];
                                    low_negative <= in_mant[71];
                                end else begin
                                    high_mag <= in_mant[71] ? -in_mant : in_mant;
                                    low_mag <= state_mant[47] ? -$signed({{24{state_mant[47]}}, state_mant}) : {{24{state_mant[47]}}, state_mant};
                                    high_negative <= in_mant[71];
                                    low_negative <= state_mant[47];
                                end
                                state <= S_SETUP;
                            end
                        end
                    end
                    S_ALIGN: begin
                        aligned_old <= $signed({{80{old_mant[47]}}, old_mant}) <<< old_shift;
                        aligned_term <= $signed({{56{term_mant[71]}}, term_mant}) <<< term_shift;
                        state <= S_SUM;
                    end
                    S_SUM: begin
                        exact_sum <= aligned_old + aligned_term;
                        state <= S_ABS;
                    end
                    S_ABS: begin
                        negative <= exact_sum[127];
                        window <= exact_sum[127] ? -exact_sum : exact_sum;
                        state <= S_LEAD;
                    end
                    S_SETUP: begin
                        high_offset <= -$signed(gap);
                        high_larger <= larger_compare;
                        negative <= larger_compare ? high_negative : low_negative;
                        subtract_mode <= high_negative != low_negative;
                        chunk_count <= (gap + 17'd136) >> 6;
                        chunk_index <= 0;
                        previous_chunk <= 0;
                        low_sticky <= 0;
                        carry_borrow <= 0;
                        state <= S_CHUNK;
                    end
                    S_CHUNK: begin
                        high_offset <= high_offset + 17'sd64;
                        carry_borrow <= chunk_arithmetic[64];
                        if (chunk_result != 0) begin
                            window <= {chunk_result, previous_chunk};
                            window_base <= chunk_position - 17'sd64;
                            magnitude_length <= chunk_position + {9'd0, bit_length({64'd0, chunk_result})};
                            sticky <= low_sticky;
                            is_power_two <= single_bit({64'd0, chunk_result}) && previous_chunk == 0 && !low_sticky;
                        end
                        low_sticky <= low_sticky || previous_chunk != 0;
                        previous_chunk <= chunk_result;
                        chunk_index <= chunk_index + 1'b1;
                        if (chunk_index + 1'b1 == chunk_count) begin
                            if (chunk_arithmetic[64]) begin
                                fault <= 1;
                                error_code <= 8'h40;
                                state <= S_IDLE;
                            end else begin
                                state <= S_LEAD;
                            end
                        end
                    end
                    S_LEAD: begin
                        if (relative_shift < 0 || relative_shift > 127) begin
                            fault <= 1;
                            error_code <= 8'h40;
                            state <= S_IDLE;
                        end else begin
                            norm_shift <= initial_shift;
                            round_shift <= relative_shift[7:0];
                            state <= S_ROUND;
                        end
                    end
                    S_ROUND: begin
                        rounded <= round_window(window, round_shift, sticky);
                        state <= S_CHECK;
                    end
                    S_CHECK: begin
                        if (rounded > (negative ? 49'd140737488355328 : 49'd140737488355327)) begin
                            if (retried) begin
                                fault <= 1;
                                error_code <= 8'h40;
                                state <= S_IDLE;
                            end else begin
                                norm_shift <= norm_shift + 1'b1;
                                round_shift <= round_shift + 1'b1;
                                retried <= 1;
                                state <= S_ROUND;
                            end
                        end else begin
                            state <= S_COMMIT;
                        end
                    end
                    S_COMMIT: begin
                        if (result_exponent < -17'sd32768 || result_exponent > 17'sd32767) begin
                            fault <= 1;
                            error_code <= 8'h32;
                        end else begin
                            state_mant <= negative ? -$signed(rounded) : $signed(rounded);
                            state_exp <= result_exponent[15:0];
                            update_pending <= 1;
                        end
                        state <= S_IDLE;
                    end
                    S_ZERO: begin
                        update_pending <= 1;
                        state <= S_IDLE;
                    end
                    default: begin
                        fault <= 1;
                        error_code <= 8'h40;
                        state <= S_IDLE;
                    end
                endcase
            end
        end
    end
endmodule
