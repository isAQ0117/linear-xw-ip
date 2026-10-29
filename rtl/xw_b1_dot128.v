`timescale 1ns / 1ps

/* 8-lane exact Q9 dot；单Block在途，乘法与三级加法树可每拍推进。 */
module xw_b1_dot128 (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                abort,
    input  wire                in_valid,
    output wire                in_ready,
    input  wire [143:0]         in_x,
    input  wire [63:0]          in_w,
    input  wire [7:0]           in_mask,
    input  wire signed [7:0]    in_exp,
    input  wire [15:0]          in_block,
    input  wire [3:0]           in_slice,
    input  wire                in_last,
    output wire                out_valid,
    input  wire                out_ready,
    output reg signed [47:0]   out_raw,
    output reg signed [7:0]    out_exp,
    output reg [15:0]          out_block,
    output reg                 fault,
    output reg [7:0]           error_code
);

    /* 数据、归属和输入顺序寄存器。 */
    reg signed [36:0] product [0:7];
    reg signed [37:0] pair_sum [0:3];
    reg signed [38:0] half_sum [0:1];
    reg signed [39:0] slice_sum;
    reg [3:0] valid_pipe;
    reg [3:0] first_pipe;
    reg [3:0] last_pipe;
    reg [15:0] block_pipe [0:3];
    reg signed [7:0] exp_pipe [0:3];
    reg signed [47:0] accumulator;
    reg [3:0] expected_slice;
    reg [15:0] active_block;
    reg signed [7:0] active_exp;
    reg closed;
    reg out_pending;
    reg [7:0] input_error;
    wire accept;
    wire signed [47:0] extended_sum;
    wire signed [47:0] accumulated;
    integer lane;
    integer p;

    /* 原始E4M3FN到signed19 Q9；无效lane在乘法前置零。 */
    function signed [18:0] decode_q9;
        input [7:0] code;
        reg [18:0] magnitude;
        begin
            magnitude = code[6:3] == 0 ? {16'd0, code[2:0]} :
                        ({15'd0, 1'b1, code[2:0]} << (code[6:3] - 1'b1));
            decode_q9 = code[7] ? -$signed(magnitude) : $signed(magnitude);
        end
    endfunction

    assign in_ready = rst_n && !abort && !fault && !closed && !out_pending;
    assign out_valid = rst_n && !abort && !fault && out_pending;
    assign accept = in_valid && in_ready;
    assign extended_sum = {{8{slice_sum[39]}}, slice_sum};
    assign accumulated = first_pipe[3] ? extended_sum : accumulator + extended_sum;

    /* 输入协议先于数值错误；只检查真正有效的FP8字节。 */
    always @(*) begin
        input_error = 8'd0;
        if (in_slice != expected_slice ||
            (in_slice != 0 && (in_block != active_block || in_exp != active_exp)) ||
            (in_slice == 15 && !in_last)) begin
            input_error = 8'h40;
        end else begin
            for (lane = 0; lane < 8; lane = lane + 1) begin
                if (in_mask[lane] && (in_w[lane*8 +: 7] == 7'h7f))
                    input_error = 8'h31;
            end
        end
    end

    /* valid与全部sideband同级移动；错误/abort清空整个Block。 */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_pipe <= 0;
            first_pipe <= 0;
            last_pipe <= 0;
            accumulator <= 0;
            expected_slice <= 0;
            active_block <= 0;
            active_exp <= 0;
            closed <= 0;
            out_pending <= 0;
            out_raw <= 0;
            out_exp <= 0;
            out_block <= 0;
            fault <= 0;
            error_code <= 0;
            for (p = 0; p < 4; p = p + 1) begin
                block_pipe[p] <= 0;
                exp_pipe[p] <= 0;
            end
        end else if (fault || abort || (accept && input_error != 0)) begin
            valid_pipe <= 0;
            out_pending <= 0;
            closed <= 1;
            if (!fault) begin
                fault <= 1;
                error_code <= abort ? 8'h40 : input_error;
            end
        end else begin
            valid_pipe <= {valid_pipe[2:0], accept};
            first_pipe <= {first_pipe[2:0], in_slice == 0};
            last_pipe <= {last_pipe[2:0], in_last};
            block_pipe[0] <= in_block;
            exp_pipe[0] <= in_exp;
            for (p = 1; p < 4; p = p + 1) begin
                block_pipe[p] <= block_pipe[p-1];
                exp_pipe[p] <= exp_pipe[p-1];
            end
            if (accept) begin
                expected_slice <= in_slice + 1'b1;
                if (in_slice == 0) begin
                    active_block <= in_block;
                    active_exp <= in_exp;
                end
                if (in_last)
                    closed <= 1;
            end
            if (valid_pipe[3]) begin
                accumulator <= accumulated;
                if (last_pipe[3]) begin
                    out_pending <= 1;
                    out_raw <= accumulated;
                    out_exp <= exp_pipe[3];
                    out_block <= block_pipe[3];
                end
            end
            if (out_valid && out_ready) begin
                out_pending <= 0;
                expected_slice <= 0;
                closed <= 0;
            end
        end
    end

    /* 乘法和树数据不复位；仅由对应valid授权消费，便于DSP寄存器推断。 */
    always @(posedge clk) begin
        if (accept) begin
            for (p = 0; p < 8; p = p + 1)
                product[p] <= in_mask[p] ? $signed(in_x[p*18 +: 18]) * decode_q9(in_w[p*8 +: 8]) : 37'sd0;
        end
        if (valid_pipe[0]) begin
            for (p = 0; p < 4; p = p + 1)
                pair_sum[p] <= {product[p*2][36], product[p*2]} + {product[p*2+1][36], product[p*2+1]};
        end
        if (valid_pipe[1]) begin
            for (p = 0; p < 2; p = p + 1)
                half_sum[p] <= {pair_sum[p*2][37], pair_sum[p*2]} + {pair_sum[p*2+1][37], pair_sum[p*2+1]};
        end
        if (valid_pipe[2])
            slice_sum <= {half_sum[0][38], half_sum[0]} + {half_sum[1][38], half_sum[1]};
    end
endmodule
