---
name: verilog-rtl-house-style
description: 为 FPGA/ASIC 项目的纯 Verilog-2001 RTL 编写、格式统一、审查和修改提供固定代码风格。用于创建或重排 .v 模块、子模块、测试平台与 xW/Linear/FFN RTL：采用 module 括号内逐端口 input/output/inout ANSI 声明、FFN 风格四空格缩进、接口后集中声明模块级 localparam/wire/reg、按功能分组注释、每个 always 块前解释作用，并在重排时严格保持时序、位宽和行为不变。适用于 Vivado 2023.2 与旧 ModelSim 的 Verilog 兼容要求。
---

# Verilog RTL 统一排版与最小风险重构

## 强制规则（每次编写或修改 RTL 都要执行）

1. 使用纯 **Verilog-2001**，不使用 SystemVerilog 的 `logic`、`always_ff`、`always_comb`、`typedef`、`interface`、`enum`、`int` 等。保留原文件必要的 `timescale`、宏、`include`、模块名与 parameter。
2. 模块端口采用 ANSI 风格：`module name #(parameter ...) (` 之后**直接**逐行写 `input  wire ...`、`output wire ...`、`output reg ...`、`inout wire ...`，端口在右括号后以 `);` 结束；不要先列端口名再在模块体里声明 `input/output`。每个端口各占一行，明确写方向和 net/variable 类型。
3. 端口按用途分组（时钟复位 → 配置/任务 → 数据通路 → DDR/AXIS → 状态），**保持原有端口顺序**（如仅排版）和原有名称、方向、位宽、signed 属性；原端口组顺序不变时优先保留。
4. `);` 后第一段集中声明**全部模块级内部常量与信号**（`localparam`、`parameter`、`wire`、`reg`、`integer`、存储数组、状态、事件等）。内部信号按职责分组，组前放一个说明性注释。**不得在任何 `assign`、`always`、`initial`、函数/任务定义、模块例化之后追加模块级声明。** 允许 Verilog 在过程块、函数、generate 局部作用域依法需要的局部声明，不能误提到模块级。
5. 声明区结束后才开始结构/逻辑区：组合连线 `assign`、子模块例化、`always @(*)`、`always @(posedge clk)` / 其他过程块。相关逻辑块聚在一起；每个 `always` 前给出一条或一个块注释，写清用途、更新条件或时序含义，不要只写“always 块”。
6. 一级缩进为 **4 个空格**，禁用 Tab。`module` 端口和主体声明缩进 4 空格，`always` 的 `if/case` 内逐层增加 4 空格。端口方向和 `wire/reg` 可以空格列对齐；连接 `.port(signal)` 保留 FFN 风格对齐。每组之间留 1 个空行；尽量不改动已有合理注释。
7. 注释内容使用简洁中文解释**职责**（按原项目约定可保留英文协议术语），采用与 FFN 示例一致的 `/* ... */` 功能分区，复杂块可用等号分隔行。不要因每个信号加逐条注释而使代码冗长。
8. 仅要求“格式调整”时，**绝对不要**重构 FSM、变动 `=`/`<=`、复位极性、延迟周期、握手、运算符、有符号性、常数、地址计算、端口 ABI、参数含义、memory 深度，或因想优化而改时序。将纯排版与功能改动分别交付，后者需要单独说明。注意 Verilog 隐式网线、宏条件、作用域和 generate 块，避免擅自移动产生语义变化。
9. 本项目既定的 `xW`/B3-B-FP32 语义只是需要**保护**的规格：FP32 Scale 原始位模式、B1 signed48、B2 signed72 Term、BFP18 AXIS、DDR 六信号 Range Read 等。**排版任务不得顺便改任何一项。**

## 工作流程

1. **输入审计**：读取待改 `.v` 和被指明的 FFN 风格参考，确认完整源码存在；记录模块/端口、参数、宏、`include`、过程块和文件列表。若只有文件名/先前下载链接而没有源码，不要编造“已修改”版；说明缺少源文件，仍可交付风格规范/Skill。
2. **格式迁移**：逐模块将旧式端口拆分声明改成括号内 ANSI 声明；把模块级信号声明按组移至模块头 `);` 之后（不可移动局部声明），以功能分区注释分隔；为每个 `always` 添加描述；统一四空格与对齐。遇到 Verilog 预处理条件、宏展开端口、声明依赖和局部作用域时，先辨别再移动。
3. **风格检查**：运行 `python scripts/check_rtl_style.py <rtl目录或文件>`；补齐工具标记的 ANSI、声明位置、Tab 和 `always` 注释问题。检查脚本做静态风格审查，**不是 HDL 编译器**；把它的告警与真实语法错误区别开。
4. **功能保护**：重排前后对比端口列表、`parameter`、宏、赋值和运算表达式、always 敏感列表与状态机。可用的环境中再执行 Icarus/ModelSim/Verilator 编译与原测试平台仿真、Golden 对比。没有工具时明确报告“只通过静态检查，未执行 HDL 仿真/综合”，绝不声称功能等价已证明。
5. **交付**：提供所有修改后的完整 `.v`（项目若为 ZIP 则保持目录层级压缩），列明改动属于纯格式变更并附静态/仿真验证结果。不要仅贴部分代码或宣称未可访问的旧文件已经修改。

## 参考与工具

- 阅读 `references/rtl_style_examples.md` 查看合格的端口、声明和组合/时序块排列，以及容易出错的旧式示例。
- 新建模块时可复制 `assets/verilog2001_module_template.v`，替换演示端口和信号后实现真正逻辑。该文件是独立的**样例模块**，不是 `xW` 原始设计。
- `scripts/check_rtl_style.py` 支持文件/目录/多个路径以及 `--json`，适用于提交前检查；其局限性见参考文件，不允许仅以该脚本通过代替仿真。
