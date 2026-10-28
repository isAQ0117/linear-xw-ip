// Verilog-2001 static/dynamic dimension descriptor latch.
// No SystemVerilog constructs. N/K computation widths include +padding carry.
module xw_job_dim_cfg #(
    parameter integer STATIC_DIM_MODE = 1,
    parameter integer N_DIM = 12288,
    parameter integer K_DIM = 4096,
    parameter integer MAX_N = 12288,
    parameter integer MAX_K = 12288
) (
    /*
     * =========================================================
     * 时钟与复位
     * =========================================================
     */
    input  wire                 clk,
    input  wire                 rst_n,

    /*
     * =========================================================
     * 任务配置接口
     * =========================================================
     */
    input  wire                 job_accept,
    input  wire [15:0]          job_n,
    input  wire [15:0]          job_k,

    /*
     * =========================================================
     * 配置状态与长度输出
     * =========================================================
     */
    output reg                  cfg_valid,
    output reg                  cfg_error,
    output reg  [15:0]          active_n,
    output reg  [15:0]          active_k,
    output wire [9:0]           n_groups,
    output wire [9:0]           k_blocks,
    output wire [10:0]          weight_words_per_row,
    output wire [5:0]           scale_words_per_group
);

    /*
     * =========================================================
     * 尺寸扩展：为向上取整计算保留进位
     * =========================================================
     */
    wire [16:0] n_extended;
    wire [16:0] k_extended;

    /*
     * 将 N/K 扩展到 17 bit，再计算 Group/Block 和 DDR Beat 数。
     */
    assign n_extended = {1'b0,active_n};
    assign k_extended = {1'b0,active_k};

    assign n_groups            = (n_extended + 17'd127) >> 7;
    assign k_blocks            = (k_extended + 17'd127) >> 7;
    assign weight_words_per_row= (k_extended + 17'd63)  >> 6;
    // ceil(ceil(K/128)/16) == ceil(K/2048)
    assign scale_words_per_group = (k_extended + 17'd2047) >> 11;

    /*
     * 任务配置锁存：复位时清零，job_accept 时选择静态或动态 N/K。
     * 同时生成 cfg_valid 和 cfg_error；保持原有时序与优先级。
     */
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cfg_valid <= 1'b0;
            cfg_error <= 1'b0;
            active_n <= 16'd0;
            active_k <= 16'd0;
        end else begin
            cfg_valid <= 1'b0;
            if (job_accept) begin
                cfg_valid <= 1'b1;
                if (STATIC_DIM_MODE != 0) begin
                    active_n <= N_DIM;
                    active_k <= K_DIM;
                    cfg_error <= (N_DIM < 1 || N_DIM > 65535 ||
                                  K_DIM < 1 || K_DIM > 65535);
                end else begin
                    active_n <= job_n;
                    active_k <= job_k;
                    cfg_error <= (job_n == 0 || job_k == 0 ||
                                  job_n > MAX_N || job_k > MAX_K);
                end
            end
        end
    end
endmodule
