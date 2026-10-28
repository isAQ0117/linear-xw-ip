// Linear xW: static/dynamic N/K latch and DDR length generation.
// Stage 1 contract: XW-CONTRACT-STD-001 V1.0; Verilog-2001, ANSI ports.
module xw_job_dim_cfg #(
    parameter integer STATIC_DIM_MODE = 1,
    parameter integer N_DIM          = 12288,
    parameter integer K_DIM          = 4096,
    parameter integer MAX_N          = 12288,
    parameter integer MAX_K          = 12288
)(
    input  wire        clk,
    input  wire        rst_n,

    // Job 输入：由上级控制器在时钟上升沿确认接收。
    input  wire        job_accept,
    input  wire [15:0] job_n,
    input  wire [15:0] job_k,

    // 输出配置结果：cfg_valid 为单拍，cfg_error 保留最近一次检查结果。
    output reg         cfg_valid,
    output reg         cfg_error,
    output reg  [15:0] active_n,
    output reg  [15:0] active_k,
    output wire  [9:0] n_groups,
    output wire  [9:0] k_blocks,
    output wire [10:0] weight_words_per_row,
    output wire  [5:0] scale_words_per_group
);

    /*
     * =========================================================
     * 编译期参数合法性检查。
     * =========================================================
     * This intentionally undefined instance makes illegal parameter
     * combinations fail ELABORATION, including synthesis elaboration.
     * Runtime invalid dynamic dimensions are handled by cfg_error.
     */
    generate
        if ((STATIC_DIM_MODE != 0 && STATIC_DIM_MODE != 1) ||
            (N_DIM < 1 || N_DIM > 65535) ||
            (K_DIM < 1 || K_DIM > 65535) ||
            (MAX_N < 1 || MAX_N > 65535) ||
            (MAX_K < 1 || MAX_K > 65535) ||
            (STATIC_DIM_MODE == 1 &&
             ((N_DIM > MAX_N) || (K_DIM > MAX_K)))) begin : g_invalid_parameters
            XW_INVALID_JOB_DIM_CFG_PARAMETERS u_must_fail_elaboration ();
        end
    endgenerate

    /*
     * =========================================================
     * N/K 分组数量与 DDR Beat 数量；使用 17-bit 中间量避免进位丢失。
     * =========================================================
     */
    wire [16:0] n_extended;
    wire [16:0] k_extended;

    assign n_extended = {1'b0, active_n};
    assign k_extended = {1'b0, active_k};

    assign n_groups             = (n_extended + 17'd127)  >> 7;
    assign k_blocks             = (k_extended + 17'd127)  >> 7;
    assign weight_words_per_row = (k_extended + 17'd63)   >> 6;
    // ceil(ceil(K / 128) / 16) = ceil(K / 2048).
    assign scale_words_per_group = (k_extended + 17'd2047) >> 11;

    /*
     * =========================================================
     * 尺寸选择与合法性检查。
     * =========================================================
     * STATIC_DIM_MODE=1: physical job_n/job_k are ignored entirely.
     * cfg_valid=1 signals that the check RESULT is available; a
     * rejected job still asserts cfg_valid together with cfg_error.
     * The controller must use cfg_valid && !cfg_error before running.
     * cfg_error holds until the next job_accept or reset.
     */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cfg_valid <= 1'b0;
            cfg_error <= 1'b0;
            active_n  <= 16'd0;
            active_k  <= 16'd0;
        end else begin
            cfg_valid <= 1'b0;
            if (job_accept) begin
                cfg_valid <= 1'b1;
                if (STATIC_DIM_MODE == 1) begin
                    active_n  <= N_DIM;
                    active_k  <= K_DIM;
                    // Static parameter validity is enforced at elaboration.
                    cfg_error <= 1'b0;
                end else begin
                    active_n  <= job_n;
                    active_k  <= job_k;
                    cfg_error <= (job_n == 16'd0 || job_k == 16'd0 ||
                                  job_n > MAX_N || job_k > MAX_K);
                end
            end
        end
    end
endmodule
