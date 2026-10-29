`timescale 1ns / 1ps

/*
 * 格式示例（非 xW 功能模块）：
 * 使用 ANSI 端口，所有模块级声明集中于 module 头之后。
 */
module rtl_style_example #(
    parameter integer DATA_WIDTH = 32
) (
    input  wire                  clk,
    input  wire                  rst_n,

    /*
     * =========================================================
     * 任务控制接口
     * =========================================================
     */
    input  wire                  start,
    output wire                  busy,

    /*
     * =========================================================
     * 数据输出接口
     * =========================================================
     */
    output reg  [DATA_WIDTH-1:0] data_out
);

    /*
     * =========================================================
     * 状态定义和寄存器
     * =========================================================
     */
    localparam [1:0] S_IDLE = 2'd0;
    localparam [1:0] S_RUN  = 2'd1;

    reg [1:0] state;

    /*
     * =========================================================
     * 任务接受与组合结果
     * =========================================================
     */
    wire start_accept;
    reg  [DATA_WIDTH-1:0] data_next;

    /*
     * 任务握手和忙状态。
     */
    assign start_accept = start && (state == S_IDLE);
    assign busy = (state != S_IDLE);

    /*
     * 组合计算下一拍输出数据。
     */
    always @(*) begin
        data_next = data_out;
        if (state == S_RUN) begin
            data_next = data_out + {{(DATA_WIDTH-1){1'b0}}, 1'b1};
        end
    end

    /*
     * 状态机及数据输出寄存器：低有效同步复位。
     */
    always @(posedge clk) begin
        if (!rst_n) begin
            state    <= S_IDLE;
            data_out <= {DATA_WIDTH{1'b0}};
        end else begin
            case (state)
                S_IDLE: begin
                    if (start_accept)
                        state <= S_RUN;
                end
                S_RUN: begin
                    data_out <= data_next;
                    state    <= S_IDLE;
                end
                default: begin
                    state <= S_IDLE;
                end
            endcase
        end
    end

endmodule
