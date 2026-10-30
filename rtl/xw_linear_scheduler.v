`timescale 1ns / 1ps

/* 正式单Job所有权与顺序调度；子模块完成只按真实握手/提交事件推进。 */
module xw_linear_scheduler #(
    parameter integer STATIC_DIM_MODE = 1,
    parameter integer N_DIM = 12288,
    parameter integer K_DIM = 4096,
    parameter integer MAX_N = 12288,
    parameter integer MAX_K = 12288
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         job_valid,
    output wire         job_ready,
    input  wire [31:0]  job_id,
    input  wire [15:0]  job_m,
    input  wire [15:0]  job_n,
    input  wire [15:0]  job_k,
    input  wire [7:0]   job_m_tile,
    input  wire [28:0]  job_weight_base,
    input  wire [28:0]  job_scale_base,
    output reg          busy,
    output reg [31:0]   active_id,
    output reg [15:0]   active_n,
    output reg [15:0]   active_k,
    output reg [28:0]   weight_base,
    output reg [28:0]   scale_base,
    output reg [15:0]   channel,
    output reg [8:0]    group_index,
    output wire         cfg_begin,
    input  wire         cfg_done,
    input  wire         cfg_error,
    input  wire [7:0]   cfg_error_code,
    input  wire         datapath_online,
    output wire         job_start,
    input  wire         stage5_ready,
    input  wire         x_loaded,
    input  wire         input_done,
    output reg          x_complete,
    output wire         load_valid,
    input  wire         load_ready,
    output wire         load_kind,
    output wire [15:0]  load_index,
    input  wire         load_done,
    output wire         compute_valid,
    input  wire         compute_ready,
    input  wire         result_valid,
    input  wire         result_ready,
    input  wire         group_done,
    input  wire [8:0]   committed_group,
    input  wire         job_results_ready,
    output wire         output_start,
    input  wire         output_ready,
    input  wire         output_done,
    output wire         finish_valid,
    input  wire         finish_ready,
    output wire         finish_ok,
    output wire [7:0]   finish_code,
    input  wire         status_accept,
    input  wire         fault_valid,
    input  wire [7:0]   fault_code,
    input  wire         fault_system,
    input  wire         clean_boundary,
    output reg [7:0]    first_error,
    output reg          fault_lock,
    output wire         cancel_datapath,
    output wire         clear_datapath
);
    /* 唯一Job所有权，配置与状态在局部清理域之外保持。 */
    localparam [4:0] S_IDLE = 0, S_DIMS = 1, S_CFG = 2, S_CHECK = 3,
                     S_START = 4, S_X = 5, S_SCALE_REQ = 6, S_SCALE_WAIT = 7,
                     S_WEIGHT_REQ = 8, S_WEIGHT_WAIT = 9, S_COMPUTE_REQ = 10,
                     S_RESULT = 11, S_GROUP = 12, S_PUBLISH = 13,
                     S_OUTPUT_START = 14, S_OUTPUT_WAIT = 15, S_FINISH = 16,
                     S_STATUS = 17, S_CLEAN = 18, S_REARM = 19, S_LOCK = 20;
    reg [4:0] state;
    reg [15:0] active_m;
    reg [7:0] active_tile;
    reg started;
    wire accept;
    wire dims_valid;
    wire dims_error;
    wire [15:0] dims_n;
    wire [15:0] dims_k;
    wire all_ready;
    wire operational;
    wire local_fault;
    wire observed_fault;
    wire [7:0] observed_code;
    wire observed_lock;

    assign job_ready = rst_n && datapath_online && state == S_IDLE && !fault_lock && !fault_valid;
    assign accept = job_valid && job_ready;
    assign all_ready = datapath_online && stage5_ready && compute_ready && output_ready;
    assign local_fault = state > S_LOCK || (state == S_GROUP && group_done && committed_group != group_index);
    assign observed_fault = fault_valid || local_fault;
    assign observed_code = fault_valid && (fault_system || !local_fault) ?
                           (fault_code == 0 ? 8'h40 : fault_code) : 8'h40;
    assign observed_lock = local_fault || fault_system || !clean_boundary || observed_code == 8'h40;
    assign operational = rst_n && !first_error && !fault_lock && !observed_fault;
    assign cfg_begin = operational && state == S_CFG;
    assign job_start = operational && state == S_START && all_ready;
    assign load_valid = operational && (state == S_SCALE_REQ || state == S_WEIGHT_REQ);
    assign load_kind = state == S_WEIGHT_REQ;
    assign load_index = load_kind ? channel : {7'd0, group_index};
    assign compute_valid = operational && state == S_COMPUTE_REQ;
    assign output_start = operational && state == S_OUTPUT_START;
    assign finish_valid = rst_n && state == S_FINISH && (first_error != 0 || !observed_fault);
    assign finish_ok = first_error == 0;
    assign finish_code = first_error;
    assign cancel_datapath = busy && started && first_error != 0;
    assign clear_datapath = state == S_CLEAN;

    xw_job_dim_cfg #(.STATIC_DIM_MODE(STATIC_DIM_MODE), .N_DIM(N_DIM), .K_DIM(K_DIM),
        .MAX_N(MAX_N), .MAX_K(MAX_K)) dimensions (
        .clk(clk), .rst_n(rst_n), .job_accept(accept), .job_n(job_n), .job_k(job_k),
        .cfg_valid(dims_valid), .cfg_error(dims_error), .active_n(dims_n), .active_k(dims_k),
        .n_groups(), .k_blocks(), .weight_words_per_row(), .scale_words_per_group()
    );

    /* 首码不覆盖；后到真实系统故障仅升级lock，终态槽不被局部清理。 */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            busy <= 0;
            active_id <= 0;
            active_n <= 0;
            active_k <= 0;
            active_m <= 0;
            active_tile <= 0;
            weight_base <= 0;
            scale_base <= 0;
            channel <= 0;
            group_index <= 0;
            first_error <= 0;
            fault_lock <= 0;
            started <= 0;
            x_complete <= 0;
        end else begin
            if (observed_fault && observed_lock)
                fault_lock <= 1;
            if (observed_fault && !busy) begin
                state <= S_LOCK;
                fault_lock <= 1;
            end else if (observed_fault && first_error == 0 && state != S_STATUS) begin
                first_error <= observed_code;
                state <= S_FINISH;
            end else begin
                case (state)
                    S_IDLE: begin
                        if (accept) begin
                            busy <= 1;
                            active_id <= job_id;
                            active_m <= job_m;
                            active_tile <= job_m_tile;
                            weight_base <= job_weight_base;
                            scale_base <= job_scale_base;
                            channel <= 0;
                            group_index <= 0;
                            first_error <= 0;
                            x_complete <= 0;
                            started <= 0;
                            state <= S_DIMS;
                        end
                    end
                    S_DIMS: begin
                        if (dims_valid) begin
                            active_n <= dims_n;
                            active_k <= dims_k;
                            if (dims_error) begin
                                first_error <= 8'h01;
                                state <= S_FINISH;
                            end else if (active_m != 1 || active_tile != 1) begin
                                first_error <= 8'h02;
                                state <= S_FINISH;
                            end else begin
                                state <= S_CFG;
                            end
                        end
                    end
                    S_CFG: state <= S_CHECK;
                    S_CHECK: begin
                        if (cfg_done) begin
                            if (cfg_error) begin
                                first_error <= cfg_error_code;
                                state <= S_FINISH;
                            end else begin
                                state <= S_START;
                            end
                        end
                    end
                    S_START: begin
                        if (job_start) begin
                            started <= 1;
                            state <= S_X;
                        end
                    end
                    S_X: begin
                        if (x_loaded && input_done) begin
                            x_complete <= 1;
                            state <= S_SCALE_REQ;
                        end
                    end
                    S_SCALE_REQ: if (load_valid && load_ready) state <= S_SCALE_WAIT;
                    S_SCALE_WAIT: if (load_done) state <= S_WEIGHT_REQ;
                    S_WEIGHT_REQ: if (load_valid && load_ready) state <= S_WEIGHT_WAIT;
                    S_WEIGHT_WAIT: if (load_done) state <= S_COMPUTE_REQ;
                    S_COMPUTE_REQ: if (compute_valid && compute_ready) state <= S_RESULT;
                    S_RESULT: begin
                        if (result_valid && result_ready) begin
                            if (channel[6:0] == 127 || {1'b0, channel} + 17'd1 == {1'b0, active_n}) begin
                                state <= S_GROUP;
                            end else begin
                                channel <= channel + 1'b1;
                                state <= S_WEIGHT_REQ;
                            end
                        end
                    end
                    S_GROUP: begin
                        if (group_done) begin
                            if ({1'b0, channel} + 17'd1 == {1'b0, active_n}) begin
                                state <= S_PUBLISH;
                            end else begin
                                channel <= channel + 1'b1;
                                group_index <= group_index + 1'b1;
                                state <= S_SCALE_REQ;
                            end
                        end
                    end
                    S_PUBLISH: if (job_results_ready) state <= S_OUTPUT_START;
                    S_OUTPUT_START: if (output_start && output_ready) state <= S_OUTPUT_WAIT;
                    S_OUTPUT_WAIT: if (output_done) state <= S_FINISH;
                    S_FINISH: if (finish_valid && finish_ready) state <= S_STATUS;
                    S_STATUS: begin
                        if (status_accept) begin
                            busy <= 0;
                            state <= fault_lock || (observed_fault && observed_lock) ? S_LOCK : S_CLEAN;
                        end
                    end
                    S_CLEAN: begin
                        started <= 0;
                        x_complete <= 0;
                        state <= S_REARM;
                    end
                    S_REARM: begin
                        if (all_ready) begin
                            first_error <= 0;
                            state <= S_IDLE;
                        end
                    end
                    S_LOCK: state <= S_LOCK;
                    default: begin
                        first_error <= first_error == 0 ? 8'h40 : first_error;
                        fault_lock <= 1;
                        state <= busy ? S_FINISH : S_LOCK;
                    end
                endcase
            end
        end
    end
endmodule
