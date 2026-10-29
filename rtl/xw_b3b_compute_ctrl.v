`timescale 1ns / 1ps

/* Stage4局部单通道计算；不加载DDR、不Requant、不发布全局Job Status。 */
module xw_b3b_compute_ctrl #(
    parameter integer MAX_K = 12288
) (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                abort,
    input  wire                req_valid,
    output wire                req_ready,
    input  wire [31:0]          req_job,
    input  wire [15:0]          req_channel,
    input  wire [15:0]          req_k,
    input  wire                x_loaded,
    input  wire                w_loaded,
    input  wire                s_loaded,
    input  wire                upstream_fault,
    input  wire [7:0]           upstream_code,
    input  wire                slice_enable,
    output wire                x_rd_req,
    output wire [15:0]          x_rd_index,
    input  wire                x_rd_valid,
    input  wire [143:0]         x_rd_data,
    input  wire [7:0]           x_rd_exp,
    input  wire [7:0]           x_rd_mask,
    output wire                w_rd_req,
    output wire [15:0]          w_rd_index,
    input  wire                w_rd_valid,
    input  wire [63:0]          w_rd_data,
    input  wire [7:0]           w_rd_mask,
    output wire                s_rd_req,
    output wire [15:0]          s_rd_index,
    input  wire                s_rd_valid,
    input  wire [31:0]          s_rd_bits,
    output wire                result_valid,
    input  wire                result_ready,
    output reg signed [47:0]   result_mant,
    output reg signed [15:0]   result_exp,
    output reg [31:0]          result_job,
    output reg [15:0]          result_channel,
    output wire                error_valid,
    output reg [7:0]           error_code,
    output reg                 fault_lock
);

    /* 局部状态、尺寸与缓存响应容量。 */
    localparam [2:0] S_IDLE = 0, S_SETUP = 1, S_RUN = 2,
                     S_WAIT = 3, S_RESULT = 4, S_FAIL = 5;
    reg [2:0] state;
    reg [31:0] active_job;
    reg [15:0] active_channel;
    reg [15:0] active_k;
    reg [15:0] total_blocks;
    reg [15:0] block_index;
    reg [4:0] issued;
    reg pending;
    reg [3:0] pending_slice;
    reg [7:0] pending_mask;
    reg pending_last;
    reg scale_pending;
    reg scale_have;
    reg [31:0] scale_bits;
    reg [252:0] responses [0:3];
    reg [1:0] write_ptr;
    reg [1:0] read_ptr;
    reg [2:0] fifo_count;
    reg error_pending;
    reg result_pending;
    reg [7:0] selected_error;
    wire active;
    wire request_accept;
    wire base_abort;
    wire pipe_abort;
    wire internal_bad;
    wire precommit_bad;
    wire a2_abort;
    wire scale_bad;
    wire scale_is_valid;
    wire [16:0] block_remaining;
    wire [4:0] slice_count;
    wire [7:0] issue_mask;
    wire issue;
    wire push;
    wire pop;
    wire [252:0] head;
    wire [143:0] head_x;
    wire [63:0] head_w;
    wire [7:0] head_exp;
    wire [7:0] head_xmask;
    wire [7:0] head_wmask;
    wire [3:0] head_slice;
    wire [15:0] head_block;
    wire head_last;
    wire b1_input;
    wire b1_ready;
    wire b1_valid;
    wire b1_out_ready;
    wire signed [47:0] b1_raw;
    wire signed [7:0] b1_exp;
    wire [15:0] b1_block;
    wire b1_fault;
    wire [7:0] b1_code;
    wire b2_ready;
    wire b2_valid;
    wire signed [71:0] b2_mant;
    wire signed [11:0] b2_exp;
    wire [15:0] b2_block;
    wire [7:0] b2_code;
    wire a2_ready;
    wire a2_update;
    wire a2_busy;
    wire signed [47:0] a2_mant;
    wire signed [15:0] a2_exp;
    wire [15:0] a2_block;
    wire a2_special;
    wire a2_fault;
    wire [7:0] a2_code;

    generate
        if (MAX_K < 1 || MAX_K > 65535) begin : g_invalid_parameters
            XW_INVALID_COMPUTE_PARAMETERS u_must_fail_elaboration ();
        end
    endgenerate

    assign active = state == S_SETUP || state == S_RUN || state == S_WAIT;
    assign base_abort = abort || error_pending || upstream_fault;
    assign pipe_abort = base_abort || selected_error != 0;
    assign req_ready = rst_n && !abort && !error_pending && !upstream_fault && state == S_IDLE;
    assign request_accept = req_valid && req_ready;
    assign result_valid = rst_n && !abort && result_pending;
    assign error_valid = rst_n && error_pending;
    assign block_remaining = {1'b0, active_k} - {block_index[9:0], 7'd0};
    assign slice_count = block_remaining >= 128 ? 5'd16 : (block_remaining + 7) >> 3;
    assign issue_mask = (issued + 1'b1 == slice_count && block_remaining < 128 && active_k[2:0] != 0) ?
                        (8'hff >> (8 - active_k[2:0])) : 8'hff;
    assign issue = rst_n && !pipe_abort && (state == S_SETUP || state == S_RUN) &&
                   issued < slice_count && ({1'b0, fifo_count} + pending < 4);
    assign x_rd_req = issue;
    assign w_rd_req = issue;
    assign x_rd_index = (block_index << 4) + {11'd0, issued};
    assign w_rd_index = x_rd_index;
    assign s_rd_req = rst_n && !pipe_abort && state == S_SETUP;
    assign s_rd_index = block_index;
    assign head = responses[read_ptr];
    assign {head_x, head_w, head_exp, head_xmask, head_wmask, head_slice, head_block, head_last} = head;
    assign b1_input = rst_n && !pipe_abort && state == S_RUN && fifo_count != 0 && slice_enable;
    assign pop = b1_input && b1_ready;
    assign push = pending && x_rd_valid && w_rd_valid && !pipe_abort;
    assign b1_out_ready = !pipe_abort && scale_have && state == S_RUN && b2_ready;
    /* 完整容量预留使pending且count=4在任何合法stall下均不可能。 */
    assign precommit_bad =
        (request_accept && (!x_loaded || !w_loaded || !s_loaded || req_k == 0 || req_k > MAX_K)) ||
        (active && (!x_loaded || !w_loaded || !s_loaded || fifo_count > 4 ||
                    (pending && fifo_count == 4) || x_rd_valid != pending || w_rd_valid != pending ||
                    s_rd_valid != scale_pending ||
                    (pending && (x_rd_mask != pending_mask || w_rd_mask != pending_mask)) ||
                    (b1_valid && (b1_block != block_index || fifo_count != 0 || pending)) ||
                    (b2_valid && b2_block != block_index)));
    assign internal_bad = precommit_bad || (active && a2_update &&
                          (state != S_WAIT || a2_block != block_index));
    assign a2_abort = base_abort || precommit_bad || scale_bad || b1_fault || a2_fault ||
                      (b2_valid && b2_code != 0);
    assign scale_bad = active && scale_pending && s_rd_valid && !scale_is_valid;

    /* 复用原模块的合法性解码；RAW=0会被综合消去乘法。 */
    xw_fp32_scale_b2 scale_precheck (
        .b1_raw(48'sd0), .act_exp(8'sd0), .scale_bits(s_rd_bits),
        .term_mant(), .term_exp(), .scale_valid(scale_is_valid)
    );

    /* 同沿系统失同步先于数值错；首错寄存后不再改写。 */
    always @(*) begin
        selected_error = 0;
        if (upstream_fault && upstream_code == 0)
            selected_error = 8'h40;
        else if (upstream_fault && upstream_code < 8'h30)
            selected_error = upstream_code;
        else if (abort || internal_bad || (b1_fault && b1_code == 8'h40) || (a2_fault && a2_code == 8'h40))
            selected_error = 8'h40;
        else if (upstream_fault)
            selected_error = upstream_code;
        else if (scale_bad || (b2_valid && b2_code != 0))
            selected_error = 8'h30;
        else if (b1_fault)
            selected_error = b1_code;
        else if (a2_fault)
            selected_error = a2_code;
    end

    xw_b1_dot128 dot128 (
        .clk(clk), .rst_n(rst_n), .abort(base_abort),
        .in_valid(b1_input), .in_ready(b1_ready), .in_x(head_x), .in_w(head_w),
        .in_mask(head_xmask & head_wmask), .in_exp(head_exp), .in_block(head_block),
        .in_slice(head_slice), .in_last(head_last), .out_valid(b1_valid), .out_ready(b1_out_ready),
        .out_raw(b1_raw), .out_exp(b1_exp), .out_block(b1_block), .fault(b1_fault), .error_code(b1_code)
    );
    xw_b2_fp32_pipe scale_pipe (
        .clk(clk), .rst_n(rst_n), .abort(base_abort),
        .in_valid(b1_valid && scale_have && state == S_RUN && !pipe_abort), .in_ready(b2_ready),
        .in_raw(b1_raw), .in_exp(b1_exp), .in_scale(scale_bits), .in_block(b1_block),
        .out_valid(b2_valid), .out_ready(a2_ready && state == S_RUN && !pipe_abort),
        .out_mant(b2_mant), .out_exp(b2_exp), .out_block(b2_block), .out_error(b2_code)
    );
    xw_a2_accum48 accumulator (
        .clk(clk), .rst_n(rst_n), .abort(a2_abort), .clear(request_accept),
        .in_valid(b2_valid && b2_code == 0 && state == S_RUN && !pipe_abort), .in_ready(a2_ready),
        .in_mant(b2_mant), .in_exp(b2_exp), .in_block(b2_block), .busy(a2_busy),
        .update_valid(a2_update), .state_mant(a2_mant), .state_exp(a2_exp), .out_block(a2_block),
        .special_path(a2_special), .fault(a2_fault), .error_code(a2_code)
    );

    /* 小FIFO仅写入完整响应条目；RAM内容不复位，count负责所有权。 */
    always @(posedge clk) begin
        if (push)
            responses[write_ptr] <= {x_rd_data, w_rd_data, x_rd_exp, x_rd_mask, w_rd_mask,
                                     pending_slice, block_index, pending_last};
    end

    /* 固定一拍响应pending随请求更新；A2提交后才重启下一Block。 */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            active_job <= 0;
            active_channel <= 0;
            active_k <= 0;
            total_blocks <= 0;
            block_index <= 0;
            issued <= 0;
            pending <= 0;
            pending_slice <= 0;
            pending_mask <= 0;
            pending_last <= 0;
            scale_pending <= 0;
            scale_have <= 0;
            scale_bits <= 0;
            write_ptr <= 0;
            read_ptr <= 0;
            fifo_count <= 0;
            error_pending <= 0;
            result_pending <= 0;
            result_mant <= 0;
            result_exp <= 0;
            result_job <= 0;
            result_channel <= 0;
            error_code <= 0;
            fault_lock <= 0;
        end else if (!error_pending && selected_error != 0) begin
            error_pending <= 1;
            error_code <= selected_error;
            fault_lock <= selected_error < 8'h30 || selected_error == 8'h40;
            pending <= 0;
            scale_pending <= 0;
            fifo_count <= 0;
            state <= result_pending && !abort ? S_RESULT : S_FAIL;
            if (abort)
                result_pending <= 0;
        end else if (abort) begin
            fault_lock <= 1;
            result_pending <= 0;
            pending <= 0;
            scale_pending <= 0;
            fifo_count <= 0;
            state <= S_FAIL;
        end else if (error_pending && state != S_RESULT) begin
            if (upstream_fault && (upstream_code < 8'h30 || upstream_code == 8'h40))
                fault_lock <= 1;
            state <= S_FAIL;
            pending <= 0;
            scale_pending <= 0;
            fifo_count <= 0;
        end else begin
            if (error_pending && upstream_fault && (upstream_code < 8'h30 || upstream_code == 8'h40))
                fault_lock <= 1;
            pending <= issue;
            scale_pending <= s_rd_req;
            if (issue) begin
                pending_slice <= issued[3:0];
                pending_mask <= issue_mask;
                pending_last <= issued + 1'b1 == slice_count;
                issued <= issued + 1'b1;
            end
            if (scale_pending && s_rd_valid) begin
                scale_bits <= s_rd_bits;
                scale_have <= 1;
            end
            if (push)
                write_ptr <= write_ptr + 1'b1;
            if (pop)
                read_ptr <= read_ptr + 1'b1;
            case ({push, pop})
                2'b10: fifo_count <= fifo_count + 1'b1;
                2'b01: fifo_count <= fifo_count - 1'b1;
                default: fifo_count <= fifo_count;
            endcase
            case (state)
                S_IDLE: begin
                    if (request_accept) begin
                        active_job <= req_job;
                        active_channel <= req_channel;
                        active_k <= req_k;
                        total_blocks <= ({1'b0, req_k} + 17'd127) >> 7;
                        block_index <= 0;
                        issued <= 0;
                        scale_have <= 0;
                        write_ptr <= 0;
                        read_ptr <= 0;
                        fifo_count <= 0;
                        state <= S_SETUP;
                    end
                end
                S_SETUP: state <= S_RUN;
                S_RUN: begin
                    if (b2_valid && a2_ready && b2_code == 0)
                        state <= S_WAIT;
                end
                S_WAIT: begin
                    if (a2_update) begin
                        if (block_index + 1'b1 == total_blocks) begin
                            result_pending <= 1;
                            result_mant <= a2_mant;
                            result_exp <= a2_exp;
                            result_job <= active_job;
                            result_channel <= active_channel;
                            state <= S_RESULT;
                        end else begin
                            block_index <= block_index + 1'b1;
                            issued <= 0;
                            scale_have <= 0;
                            state <= S_SETUP;
                        end
                    end
                end
                S_RESULT: begin
                    if (result_pending && result_ready) begin
                        result_pending <= 0;
                        state <= error_pending ? S_FAIL : S_IDLE;
                    end
                end
                S_FAIL: state <= S_FAIL;
                default: begin
                    error_pending <= 1;
                    error_code <= 8'h40;
                    fault_lock <= 1;
                    state <= S_FAIL;
                end
            endcase
        end
    end
endmodule
