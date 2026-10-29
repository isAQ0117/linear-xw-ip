`timescale 1ns / 1ps

/* Stage5局部控制：不调度DDR、不生成AXIS、不发布Job成功Status。 */
module xw_stage5_ctrl #(
    parameter integer MAX_N = 12288
) (
    input  wire                clk,
    input  wire                rst_n,
    input  wire                abort,
    input  wire                job_start,
    output wire                job_ready,
    input  wire [31:0]          job_id,
    input  wire [15:0]          job_n,
    input  wire                retire,
    input  wire                clean_boundary,
    input  wire                upstream_fault,
    input  wire [7:0]           upstream_code,
    input  wire                upstream_lock,
    input  wire                result_valid,
    output wire                result_ready,
    input  wire signed [47:0]   result_mant,
    input  wire signed [15:0]   result_exp,
    input  wire [31:0]          result_job,
    input  wire [15:0]          result_channel,
    output wire                group_done,
    output reg [31:0]          group_job,
    output reg [8:0]           group_id,
    output reg [7:0]           group_len,
    output reg signed [7:0]    group_exp,
    output wire                job_results_ready,
    output wire                error_valid,
    output reg [7:0]           error_code,
    output reg                 fault_lock,
    input  wire                rd_req,
    output wire                rd_ready,
    input  wire [15:0]          rd_word_index,
    output wire                rd_valid,
    output wire [143:0]         rd_data,
    output wire signed [7:0]    rd_exp,
    output wire [7:0]           rd_mask,
    output wire [15:0]          rd_index
);
    /* 当前Job和组游标，错误仅在本层归因。 */
    localparam [3:0] S_IDLE = 0, S_COLLECT = 1, S_WAIT = 2, S_COMMIT = 3,
                     S_PUBLISH = 4, S_NEXT = 5, S_FINAL = 6, S_COMPLETE = 7, S_FAILED = 8;
    reg [3:0] state;
    reg [31:0] active_job;
    reg [15:0] active_n;
    reg [8:0] current_group;
    reg error_pending;
    reg group_pending;
    reg [7:0] selected_error;
    wire start_accept;
    wire local_bad;
    wire stop;
    wire cancel;
    wire [16:0] remaining;
    wire [7:0] current_length;
    wire group_begin;
    wire gb_ready;
    wire gb_loaded;
    wire gb_nonzero;
    wire signed [17:0] gb_hmax;
    wire gb_fault;
    wire ram_req;
    wire [6:0] ram_index;
    wire ram_valid;
    wire signed [47:0] ram_mant;
    wire signed [15:0] ram_exp;
    wire quant_start;
    wire attempt_begin;
    wire q_valid;
    wire [6:0] q_index;
    wire signed [18:0] q_mant;
    wire q_last;
    wire quant_done;
    wire signed [7:0] quant_exp;
    wire retried;
    wire quant_fault;
    wire [7:0] quant_code;
    wire rb_fault;
    wire rb_commit;
    wire rb_visible;

    generate
        if (MAX_N < 1 || MAX_N > 65535) begin : g_invalid_parameters
            XW_INVALID_STAGE5_PARAMETERS u_must_fail_elaboration ();
        end
    endgenerate

    assign job_ready = rst_n && !abort && !upstream_fault && !error_pending && !fault_lock && state == S_IDLE;
    assign start_accept = job_start && job_ready;
    assign remaining = {1'b0, active_n} - {1'b0, current_group, 7'd0};
    assign current_length = remaining >= 128 ? 8'd128 : remaining[7:0];
    assign group_begin = start_accept || state == S_NEXT;
    assign quant_start = state == S_COLLECT && gb_loaded;
    assign local_bad = (job_start && (!job_ready || job_n == 0 || job_n > MAX_N)) ||
                       (retire && ((state != S_COMPLETE && state != S_FAILED) || !clean_boundary || fault_lock)) ||
                       (state == S_PUBLISH && !rb_commit) || state > S_FAILED;
    assign stop = abort || upstream_fault || error_pending || selected_error != 0;
    assign cancel = stop || retire;
    assign result_ready = !stop && state == S_COLLECT && gb_ready;
    assign group_done = rst_n && !stop && group_pending;
    assign job_results_ready = rst_n && !stop && rb_visible;
    assign error_valid = rst_n && error_pending;

    /* 上游已锁存根因优先；同沿本地系统错误先于新数值错误。 */
    always @(*) begin
        selected_error = 0;
        if (upstream_fault && (upstream_lock || upstream_code < 8'h30 || upstream_code == 8'h40))
            selected_error = upstream_code == 0 ? 8'h40 : upstream_code;
        else if (local_bad || gb_fault || rb_fault || (quant_fault && quant_code == 8'h40) ||
                 (abort && !upstream_fault))
            selected_error = 8'h40;
        else if (upstream_fault)
            selected_error = upstream_code;
        else if (quant_fault)
            selected_error = quant_code;
    end

    xw_output_group_buffer group_buffer (
        .clk(clk), .rst_n(rst_n), .cancel(cancel), .begin_group(group_begin && !stop),
        .group_job(start_accept ? job_id : active_job),
        .group_base(start_accept ? 16'd0 : {current_group, 7'd0}),
        .group_len(start_accept ? (job_n >= 128 ? 8'd128 : job_n[7:0]) : current_length),
        .result_valid(result_valid && state == S_COLLECT), .result_ready(gb_ready),
        .result_mant(result_mant), .result_exp(result_exp), .result_job(result_job), .result_channel(result_channel),
        .loaded(gb_loaded), .nonzero(gb_nonzero), .hmax(gb_hmax),
        .rd_req(ram_req), .rd_index(ram_index), .rd_valid(ram_valid), .rd_mant(ram_mant), .rd_exp(ram_exp), .fault(gb_fault)
    );
    xw_bfp18_requant requant (
        .clk(clk), .rst_n(rst_n), .cancel(cancel), .start(quant_start && !stop),
        .group_len(current_length), .nonzero(gb_nonzero), .hmax(gb_hmax),
        .rd_req(ram_req), .rd_index(ram_index), .rd_valid(ram_valid), .rd_mant(ram_mant), .rd_exp(ram_exp),
        .attempt_begin(attempt_begin), .q_valid(q_valid), .q_index(q_index), .q_mant(q_mant), .q_last(q_last),
        .done(quant_done), .shared_exp(quant_exp), .retried(retried), .fault(quant_fault), .error_code(quant_code)
    );
    xw_result_buffer #(.MAX_N(MAX_N)) result_buffer (
        .clk(clk), .rst_n(rst_n), .cancel(cancel), .job_begin(start_accept && !stop), .job_n(job_n),
        .attempt_begin(attempt_begin), .group_index(current_group), .group_len(current_length),
        .q_valid(q_valid), .q_index(q_index), .q_mant(q_mant[17:0]), .q_last(q_last),
        .commit(state == S_COMMIT && !stop), .commit_exp(quant_exp), .publish(state == S_FINAL && !stop),
        .group_committed(rb_commit), .job_results_ready(rb_visible),
        .rd_req(rd_req), .rd_ready(rd_ready), .rd_word_index(rd_word_index), .rd_valid(rd_valid),
        .rd_data(rd_data), .rd_exp(rd_exp), .rd_mask(rd_mask), .rd_index(rd_index), .fault(rb_fault)
    );

    /* 完成晚于最后写入及指数提交；错误优先禁止同沿成功发布。 */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            active_job <= 0;
            active_n <= 0;
            current_group <= 0;
            error_pending <= 0;
            error_code <= 0;
            fault_lock <= 0;
            group_pending <= 0;
            group_job <= 0;
            group_id <= 0;
            group_len <= 0;
            group_exp <= 0;
        end else begin
            group_pending <= 0;
            if (error_pending) begin
                state <= S_FAILED;
                if (upstream_fault && (upstream_lock || upstream_code < 8'h30 || upstream_code == 8'h40))
                    fault_lock <= 1;
                if (retire && clean_boundary && !fault_lock && !upstream_fault && !abort) begin
                    error_pending <= 0;
                    error_code <= 0;
                    state <= S_IDLE;
                end
            end else if (selected_error != 0) begin
                error_pending <= 1;
                error_code <= selected_error;
                fault_lock <= selected_error < 8'h30 || selected_error == 8'h40 || upstream_lock || !clean_boundary;
                state <= S_FAILED;
            end else if (retire) begin
                state <= S_IDLE;
            end else begin
                case (state)
                    S_IDLE: begin
                        if (start_accept) begin
                            active_job <= job_id;
                            active_n <= job_n;
                            current_group <= 0;
                            state <= S_COLLECT;
                        end
                    end
                    S_COLLECT: begin
                        if (gb_loaded)
                            state <= S_WAIT;
                    end
                    S_WAIT: begin
                        if (quant_done)
                            state <= S_COMMIT;
                    end
                    S_COMMIT: state <= S_PUBLISH;
                    S_PUBLISH: begin
                        group_pending <= 1;
                        group_job <= active_job;
                        group_id <= current_group;
                        group_len <= current_length;
                        group_exp <= quant_exp;
                        if (remaining <= 128) begin
                            state <= S_FINAL;
                        end else begin
                            current_group <= current_group + 1'b1;
                            state <= S_NEXT;
                        end
                    end
                    S_NEXT: state <= S_COLLECT;
                    S_FINAL: state <= S_COMPLETE;
                    default: begin end
                endcase
            end
        end
    end
endmodule
