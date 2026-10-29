`timescale 1ns / 1ps

/* 单条精确RNE通路；retry重新读取原始A2，最终指数才检查signed8。 */
module xw_bfp18_requant (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                cancel,
    input  wire                start,
    input  wire [7:0]           group_len,
    input  wire                nonzero,
    input  wire signed [17:0]   hmax,
    output wire                rd_req,
    output wire [6:0]           rd_index,
    input  wire                rd_valid,
    input  wire signed [47:0]   rd_mant,
    input  wire signed [15:0]   rd_exp,
    output wire                attempt_begin,
    output wire                q_valid,
    output reg [6:0]           q_index,
    output reg signed [18:0]   q_mant,
    output reg                 q_last,
    output wire                done,
    output reg signed [7:0]    shared_exp,
    output reg                 retried,
    output reg                 fault,
    output reg [7:0]           error_code
);
    /* 单组状态与固定一拍RAM在途归属。 */
    localparam [2:0] S_IDLE = 0, S_READ = 1, S_DRAIN = 2, S_CHECK = 3, S_RESTART = 4;
    reg [2:0] state;
    reg [7:0] length;
    reg [7:0] issued;
    reg pending;
    reg [6:0] pending_index;
    reg q_pending;
    reg done_pending;
    reg overflow_seen;
    reg signed [17:0] exponent;
    wire signed [18:0] rounded;
    wire bad;

    /* 幅度RNE；动态移位量先分类，只用有界5/6bit移位。 */
    function signed [18:0] quantize;
        input signed [47:0] mant;
        input signed [15:0] exp;
        input signed [17:0] target;
        reg [47:0] mag;
        reg signed [17:0] delta;
        reg [5:0] amount;
        reg [4:0] left_amount;
        reg [17:0] q;
        reg guard_bit;
        reg sticky_bit;
        begin
            mag = mant[47] ? (~mant + 48'd1) : mant;
            delta = target - $signed({{2{exp[15]}}, exp});
            amount = delta[5:0];
            left_amount = 5'd0 - delta[4:0];
            q = 0;
            guard_bit = 0;
            sticky_bit = 0;
            if (mag != 0) begin
                if (delta <= 0) begin
                    q = mag[17:0] << left_amount;
                end else if (delta < 18'sd48) begin
                    q = mag >> amount;
                    guard_bit = mag[amount - 1'b1];
                    sticky_bit = (mag << (6'd49 - amount)) != 0;
                    if (guard_bit && (sticky_bit || q[0]))
                        q = q + 1'b1;
                end
            end
            quantize = mant[47] ? -$signed({1'b0, q}) : $signed({1'b0, q});
        end
    endfunction

    assign rd_req = rst_n && !cancel && !fault && state == S_READ && issued < length;
    assign rd_index = issued[6:0];
    assign attempt_begin = rst_n && !cancel && !fault && ((start && state == S_IDLE) || state == S_RESTART);
    assign rounded = quantize(rd_mant, rd_exp, exponent);
    assign q_valid = rst_n && !cancel && !fault && q_pending;
    assign done = rst_n && !cancel && !fault && done_pending;
    assign bad = (start && (state != S_IDLE || group_len == 0 || group_len > 128)) ||
                 (rd_valid != pending) || (pending && state != S_READ && state != S_DRAIN) ||
                 (state > S_RESTART);

    /* 每拍处理上一沿RAM返回；最后q被写入的同沿执行CHECK。 */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            length <= 0;
            issued <= 0;
            pending <= 0;
            pending_index <= 0;
            q_pending <= 0;
            done_pending <= 0;
            q_index <= 0;
            q_mant <= 0;
            q_last <= 0;
            overflow_seen <= 0;
            exponent <= 0;
            shared_exp <= 0;
            retried <= 0;
            fault <= 0;
            error_code <= 0;
        end else if (cancel) begin
            state <= S_IDLE;
            pending <= 0;
            q_pending <= 0;
            done_pending <= 0;
            fault <= 0;
            error_code <= 0;
        end else if (fault || bad) begin
            if (!fault) begin
                fault <= 1;
                error_code <= 8'h40;
            end
            state <= S_IDLE;
            pending <= 0;
            q_pending <= 0;
            done_pending <= 0;
        end else begin
            pending <= rd_req;
            q_pending <= rd_valid;
            done_pending <= 0;
            if (rd_req) begin
                pending_index <= issued[6:0];
                issued <= issued + 1'b1;
                if (issued + 1'b1 == length)
                    state <= S_DRAIN;
            end
            if (rd_valid) begin
                q_mant <= rounded;
                q_index <= pending_index;
                q_last <= {1'b0, pending_index} + 8'd1 == length;
                if (rounded > 19'sd131071 || rounded < -19'sd131071)
                    overflow_seen <= 1;
                if ({1'b0, pending_index} + 8'd1 == length)
                    state <= S_CHECK;
            end
            case (state)
                S_IDLE: begin
                    if (start) begin
                        length <= group_len;
                        issued <= 0;
                        overflow_seen <= 0;
                        retried <= 0;
                        exponent <= nonzero ? hmax - 18'sd16 : 18'sd0;
                        state <= S_READ;
                    end
                end
                S_CHECK: begin
                    if (overflow_seen) begin
                        if (retried) begin
                            fault <= 1;
                            error_code <= 8'h40;
                            state <= S_IDLE;
                        end else begin
                            retried <= 1;
                            exponent <= exponent + 18'sd1;
                            issued <= 0;
                            overflow_seen <= 0;
                            state <= S_RESTART;
                        end
                    end else if (exponent < -18'sd128 || exponent > 18'sd127) begin
                        fault <= 1;
                        error_code <= 8'h33;
                        state <= S_IDLE;
                    end else begin
                        shared_exp <= exponent[7:0];
                        done_pending <= 1;
                        state <= S_IDLE;
                    end
                end
                S_RESTART: state <= S_READ;
                default: begin end
            endcase
        end
    end
endmodule
