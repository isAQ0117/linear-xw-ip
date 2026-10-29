# RTL 格式规范：参照 FFN 工程，强化声明集中化

## 目标与约定

参考旧 FFN 的 `hidden_state_loader.v`、`fp8_mul.v` 和 `gemv_12288x4096_engine.v` 的版面习惯：模块括号内的端口方向+类型、功能性块注释、4 空格缩进及信号列对齐。用户另外要求：**所有模块级信号声明先于任何 `always`/`assign`/例化，不采用 FFN 示例中偶尔出现的穿插声明。**

## 推荐的文件结构

```verilog
`timescale 1ns / 1ps

module example #(
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
     * 状态机常量和寄存器
     * =========================================================
     */
    localparam [1:0] S_IDLE = 2'd0;
    localparam [1:0] S_RUN  = 2'd1;
    reg [1:0] state;

    /*
     * =========================================================
     * 任务握手与数据通路内部信号
     * =========================================================
     */
    wire start_accept;
    reg  [DATA_WIDTH-1:0] data_next;

    /*
     * 任务在空闲时被接受。
     */
    assign start_accept = start && (state == S_IDLE);
    assign busy = (state != S_IDLE);

    /*
     * 组合生成下一拍数据。
     */
    always @(*) begin
        data_next = data_out;
        if (state == S_RUN) begin
            data_next = data_out + {{(DATA_WIDTH-1){1'b0}}, 1'b1};
        end
    end

    /*
     * 状态机及输出寄存器：低有效同步复位。
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
```

此例用于演示**顺序和排版**，不是替换原 xW 计算的逻辑模板；真正设计不得复制其状态机与数据行为。

## 不接受的旧式布局

```verilog
module example (clk, rst_n, out);
    input clk;
    input rst_n;
    output reg out;
    always @(posedge clk) out <= rst_n;
    wire late_signal; // 模块级声明出现在 always 之后
endmodule
```

问题：端口不是 ANSI；`late_signal` 混在逻辑后面；`always` 前无职责注释。即使某些工具接受，也不符合本项目规范。

## 边界说明

- `reg` 不等于触发器，组合过程赋值的变量也可以是 `reg`。不要因为统一格式而擅自把组合过程 `reg` 换成 `wire`。
- 保留 `signed`、位宽表达式、四态常数、接口宽度。不要将原 `output reg` 换成 `output wire`。
- `generate` 中的 `localparam`、`wire` 和命名块内局部变量有作用域，不能全移至模块顶端；适当说明它们是局部例外。
- 若端口由 `ifdef` 控制或声明含宏，请逐分支保证 ANSI 语法成立，不要用纯字符串替换强行迁移。
- 组合 `always @(*)` 使用阻塞赋值 `=`，寄存器时序 `always @(posedge ...)` 通常用非阻塞赋值 `<=`，但格式任务不修正原有逻辑语义。
- 每个 `always` 前用一段**说明做什么**的注释；分组注释无需在每根 wire 上重复。
- 工具 `check_rtl_style.py` 是保守静态检查，不能解析全部 Verilog 宏/生成分支，也不能验证功能等价；最终必须根据条件运行 HDL 编译与 Testbench。
