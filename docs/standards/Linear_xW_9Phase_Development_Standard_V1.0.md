# Linear xW IP 九阶段开发与验收标准

**标准编号**：XW-DEV-STD-001  
**版本**：V1.0（固定开发路线）  
**生效日期**：2026-10-28  
**适用对象**：通用 FP8 / BFP18 Linear `xW` IP 的 RTL、Python 软件模型、Testbench、验证数据及交付工程  
**路线状态**：正式固定；不得在常规迭代中随意调整

> **总原则：固定九阶段开发路线；技术契约在阶段 0 收口；每一阶段软件模型、RTL 和 Testbench 协同前进。**

## 1. 适用范围与规则层级

本标准明确 *按什么顺序开发* 和 *怎样判定某阶段完成*，与 RTL House Style Skill、Source Preflight 标准互补，不替代它们。

- **路线层（本文件）**：阶段 0～8 的数量、名称、顺序、职责及验收门槛固定。
- **契约层（阶段 0 的成果）**：顶层 ABI、TUSER V2、DDR Layout V3、B3-B-FP32 数值规范、状态与错误协议、验证要求。未完成的细节必须在阶段 0 补齐，不代表可以改动九阶段路线。
- **实现层（各阶段成果）**：具体状态机、流水寄存器、RAM 推断、微架构延迟、代码模块拆分。允许在当前阶段细化，但必须遵守已冻结契约和本路线。
- **前置审计层（每次开发必做）**：实际读取源码、版本、完整性及依赖检查。当前关键源文件不可读则停止相应修改，但不重排开发阶段。

任何未经明确批准的阶段跳跃不得被记录为已通过。可为降低风险提前开展**独立研究/数值原型**，但不能将其冒充正式阶段完成。

## 2. 固定的九个开发阶段

| 阶段 | 名称 | 对外验收里程碑 |
|---|---|---|
| **0** | 冻结接口与验证契约 | Contract Baseline 具备版本号、逐项定义和验收矩阵 |
| **1** | 验证已有的四个 RTL 模块 | 现有四模块真实 HDL 编译与模块仿真通过 |
| **2** | AXIS Input + Activation Buffer | 输入 BFP18/TUSER V2、完整 X 缓存、反压测试通过 |
| **3** | DDR 地址生成 + Weight Row Buffer | DDR Layout V3 地址、Scale / Weight 数据位模式一致 |
| **4** | B1 Dot128 + B2 + A2 Accumulator | B1/B2/A2 的每个 K Block 检查点 Bit-Exact |
| **5** | BFP18 Requant + Output Buffer | 每个 N Group 的输出尾组、共享指数和 Mantissa Bit-Exact |
| **6** | AXIS Output + Job Status | 下游反压和最终状态握手满足契约 |
| **7** | Linear Scheduler + 顶层集成 | 第一个完整 M=1 Linear Job 的 RTL 端到端验证通过 |
| **8** | 多 Batch Weight Reuse + 真实权重验证 | M_TILE 分批、权重复用及 `.safetensors` 数据验证完成 |

**阶段顺序固定为 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8。**

### 阶段 0：冻结接口与验证契约

**目的**：避免后续模块接口、地址、舍入及状态协议反复返工。

工作范围：

1. 确认顶层参数、35 个物理端口的名称/方向/位宽、静态和动态 N/K 的锁存语义。
2. 整理 AXIS BFP18 18-bit 数据打包、TKEEP/TLAST、128-bit TUSER V2 和输入输出顺序。
3. 冻结六信号 DDR Range 接口、地址步长、包含式末地址、返回方式以及 DDR Layout V3。
4. 冻结 B3-B-FP32 数值 Profile：FP8 E4M3FN、FP32 Scale、B1 signed48、B2 signed72、A2 signed48/signed16、每 Block RNE、输出 BFP18。
5. 明确 Job/Status/Error、复位、协议违例、异常结束、超时/不支持条件的规则。
6. 固定数值 Golden、周期模型和 RTL 仿真的检查点、事件定义、覆盖集、通过标准。
7. 完成源文件前置审计，形成工程基线清单。

**交付**：顶层 ABI 表、AXIS/TUSER 规范、DDR/Layout 规范、数值规则、错误与复位协议、验证契约矩阵、基线 Manifest。

**退出条件**：所有影响跨模块一致性的行为有明确规范（可以声明“暂不支持”及其响应）；无悬而未决的 P0 级接口冲突；形成 `STAGE0_CONTRACT_FROZEN` 记录。此阶段**不要求**完成全部 RTL 和 HDL 运行。

### 阶段 1：验证已有的四个 RTL 模块

对象：`xw_job_dim_cfg.v`、`xw_ddr_range_rx.v`、`xw_scale_group_cache.v`、`xw_fp32_scale_b2.v`。

- 对照阶段 0 契约检查参数、I/O、时序边界、非法输入表现。
- 执行真实 HDL 编译、三个已有 Testbench，并补齐 `xw_job_dim_cfg` Testbench。
- Python 提供独立算术期望及 DDR/尺寸测试向量，RTL 自检查而非仅观察波形。
- 验证 DDR 同周期首 Beat、Beat 间隔、Scale 跨 Beat、FP32 normal/subnormal 等。

**退出条件**：四模块 HDL 编译通过、模块级 RTL 测试通过、没有未解释的数值和协议差异；记录软件与 HDL 的执行环境和结果。

### 阶段 2：AXIS Input + Activation Buffer

对象：`xw_axis_bfp18_input.v`、`xw_activation_buffer.v`。

- 接收 512-bit BFP18 Input，严格解析 TUSER V2、TKEEP、TLAST、EOT。
- 按 Row/K Group 缓存 X 及共享指数，支持后续重复读取。
- Python 同步建立**逐 Beat/逐拍**输入解析与缓存模型。
- 处理有效/无效数据、输入间隙、反压、尾组、复位后重新开始。

**退出条件**：输入数据无丢失、无重复、无错位，X Buffer 数据位模式正确；AXIS 握手及已定义异常与 Python 模型吻合。

### 阶段 3：DDR 地址生成 + Weight Row Buffer

对象：`xw_ddr_addr_gen.v`、`xw_weight_row_buffer.v`，连接已有 Receiver/Scale Cache。

- 对每个输出通道 Group，先读取全部 FP32 Scale；每条 Weight Row 读取完整 K 有效元素。
- 使用 DDR Layout V3，按有效 N/K 计算每次 Range 的地址与 Beat 数。
- 首版仅一个 Outstanding Range，不重叠 DDR 读和计算；返回无 Ready，预留完整接收空间。
- Python 同步模拟 Request 握手、Beat 到达、缓存写入/同步读和状态更新。
- 核对 DDR Manifest、地址越界、尾部 Padding、Group 重用边界。

**退出条件**：Scale/Weight 位模式、地址、请求/响应 Beat 及周期检查点一致；对 K=129、2049 等边界可重复验证。

### 阶段 4：B1 Dot128 + B2 + A2 Accumulator

对象：`xw_b1_dot128.v`、已有 `xw_fp32_scale_b2.v`、`xw_a2_accum48.v`。

- 首版 `P_N=1`、`P_K=8`，每个 K Block 最多 128 元素；B1 输出 signed48 RAW。
- B2 使用原始 FP32 Scale，输出完整 signed72 Term 与约定指数；禁止预先截断为 signed56。
- A2 按升序 K Block 更新 signed48 Mantissa / signed16 Exponent；每 Block 进行 RNE，处理抵消、大指数差、正负 ties。
- Python 建立独立定向向量与实际流水线级 Cycle Model。
- 比较 B1 RAW、B2 Term、A2 每轮结果，不能只比较最终输出 Y。

**退出条件**：全部检查点 Bit-Exact，控制时序和有效信号一致，异常输入行为满足契约。

**特别约定**：允许阶段 1 后提前开展 **A2 独立数值原型与定向测试**，以提前发现算术风险；但正式 B1/B2/A2 集成与阶段验收仍保留在阶段 4，不改变九阶段顺序。

### 阶段 5：BFP18 Requant + Output Buffer

对象：`xw_bfp18_requant.v`、`xw_output_group_buffer.v`、结果存储。

- 当前输出 N Group 的所有通道完成 A2 后，统一确定输出共享指数和 signed18 Mantissa。
- 对 N 不足 128 的尾组、正负大数、正负抵消、RNE 边界验证。
- 将最终 BFP18 结果保存到 Result Buffer，不要求持久保存完整矩阵的 A2 64-bit 状态。
- Python 同步给出逐组数值和缓存时序检查点。

**退出条件**：每个 Group 的指数和所有 Mantissa Bit-Exact；结果存储读写无串组、串行问题。

### 阶段 6：AXIS Output + Job Status

对象：`xw_axis_bfp18_output.v`，以及顶层终态协议的实现。

- Row-Major 输出，TUSER V2 与输入物理格式兼容，EOT 仅出现在最终 Beat。
- TVALID=1 且 TREADY=0 时，TDATA/TKEEP/TLAST/TUSER 必须稳定。
- 最后一个输出 Beat 完成有效握手**之后**才允许发布 Job 成功终态。
- STATUS 的 Valid/Ready、字段保持、失败条件和 Busy 释放遵守阶段 0 契约。

**退出条件**：任意输出反压下无丢失/重复；成功和失败终态与软件契约一致。

### 阶段 7：Linear Scheduler + 顶层集成

对象：`xw_linear_scheduler.v`、`linear_xw_ip.v`。

- 连接输入、DDR、计算、输出和终态模块；首个端到端场景固定 `M=1, N=2, K=129`。
- 首版顺序：全部 X 输入 → 每 N Group Scale → 每 Channel Weight Row → K Blocks B1/B2/A2 → Group Requant → Job 完成后 Row-Major AXIS 输出 → Status。
- 完成静态配置第一版，再覆盖动态 N/K、输入输出 Stall、异常重启、Job 连续接受。
- 对照数值 Golden 和微架构周期 Trace，不以 Python 架构假设延迟冒充实际 RTL 延迟。

**退出条件**：真实 RTL 端到端功能、Bit-Exact、关键协议事件及定义过的周期检查点全部符合契约。

### 阶段 8：多 Batch Weight Reuse + 真实权重验证

- 从 M=1 扩展 M=2、4，逐步实现 `M_TILE` 和跨 Tile 调度；核对权重是否正确复用或按 Tile 重读。
- 对每条 Weight Row 在 Tile 内服务多个 X Row；Row-Major 输出顺序不变。
- 使用真实模型 `.safetensors` 导出原始 FP8 bytes 和原始 FP32 Scale bit pattern，生成相同的 DDR Layout V3。
- 将误差分成三个层次：RTL/Golden Bit-Exact、已量化输入的精确 xW 误差、原始模型浮点 xW 的整体误差（有可靠原始参考才做）。
- 评估实际场景的 DDR 读次数、Buffer 上限、吞吐与可扩展性。

**退出条件**：分 Tile 和多 Batch 结果/访问计数符合参考；真实模型数据可重复加载并通过对应的数值验证。

## 3. 每个阶段统一采用的三层验证体系

**Level 1 — Independent Numeric Golden**

- 从 BFP18、FP8 E4M3FN、FP32 Scale 的数学定义独立求预期结果。
- 验证每个 B1/B2/A2 检查点与最终 BFP18 输出。
- 对 A2 的独立性需特别审查：不能只由同一份生产数值函数自我证明。

**Level 2 — Microarchitecture Cycle Model**

- 按真实微架构建立状态机、寄存器、FIFO/RAM、Ready/Valid、Latency、错误和复位。
- 每完成一个 RTL 模块，就同步细化相应的 Python 周期模型。
- 区分已冻结的**接口周期合同**与本阶段需要确定的**内部流水线实现延迟**。

**Level 3 — RTL Simulation**

- 真正编译并仿真纯 Verilog RTL。
- 同时进行 Functional Check（数值/协议）和 Cycle Check（约定的握手/状态事件周期）。
- 在后续集成中逐步扩大测试范围，不能用 Python 通过代替 HDL 通过。

通用准入/验收原则：**每个新增 RTL 模块都要有对应软件参考模型、模块级 Testbench、边界/异常向量及明确的 PASS 证据。**

## 4. 固定的首版技术基线（技术细节依阶段 0 契约为准）

- 实现模式：单 Active Job、`STATIC_DIM_MODE=1`、`M=1`、`MAX_M_TILE=1`、`P_N=1`、`P_K=8`。
- AXIS：输入输出 512-bit BFP18，TUSER V2 128-bit。
- DDR：六信号，512-bit Beat，29-bit 逻辑地址、每 Beat +8、末地址包含、一条 Outstanding Range。
- DDR Layout V3：Weight output-channel-major，每行 64B 对齐；Scale 以 128 输出通道为 Group，每 Group 独立 64B 对齐且保存原始 FP32。
- 数值：B1 signed48，B2 signed72，A2 signed48+signed16，输出 BFP18 group-128。
- 策略：先缓存完整 X 和完整 Weight Row；无 DDR/Compute 重叠；整个 Job 计算完成再输出。
- 工具与格式：Vivado 2023.2；纯 Verilog-2001 保守子集，不使用 SystemVerilog；FFN 风格 ANSI 端口、统一声明区、四空格缩进与分组注释。

这里的“首版技术基线”不等于宣布阶段 0 所有错误/复位/周期合同已签核。尚未收口项目见独立的阶段 0 审计报告。

## 5. 每阶段固定交付清单

1. 本阶段起始文件可读性审计、版本与 SHA-256 / Manifest。
2. 本阶段接口契约及差异清单。
3. 版本控制下的 Python 数值模型与微架构周期模型。
4. 纯 Verilog RTL、模块级 Testbench、可执行的复现命令。
5. Functional Check 与 Cycle Check 结果（未运行项目明确记为 Pending）。
6. 修改说明、遗留问题及阶段退出结论。
7. 阶段验收标记：`NOT_STARTED`、`IN_PROGRESS`、`BLOCKED`、`PASS`；若缺少真实 HDL 验证，不得误标 `PASS`。

## 6. 开发路线变更控制（强制）

1. **默认不调整**阶段 0～8 的数量、名称、顺序及核心目标。
2. 阶段内允许细化子模块、测试用例、软件验证方法；不允许将未完成工作无记录地挪出阶段。
3. 发现新问题先记录为对应阶段的子任务/缺陷，原则上不增加第十阶段。
4. 只有出现不可兼容的硬性约束且**用户明确批准变更**后，才可正式修订 V1.0 路线；必须说明动机、影响、迁移方案和新版本号。
5. 本标准优先于过去任何临时性的不同阶段建议。后续每次设计回答需注明**当前阶段、当前子任务、验收状态、对标准有无偏离**。
6. 已完成阶段若出现缺陷，回到相应阶段修复，不代表改变开发路线。

## 7. 当前项目状态（2026-10-28）

- **阶段 0：`IN_PROGRESS`（核心规格已大量确定，但完整契约尚未签核）**。
- **阶段 1：`IN_PROGRESS`（四个 RTL 已有源码和三个 Testbench；已提交的软件测试通过，但真实 HDL 测试尚未完成）**。
- **阶段 2～8：`NOT_STARTED`（部分 Python 行为和数值原型已有实现，不代表这些 RTL 阶段验收通过）**。
- 已上传并可实读的是格式修改前的完整 FP32 V0.2 和 RTL Starter；此前交付的 FFN-style 整理版未出现在本次可用附件中，实际源码续写前须重新核验它。

**下一项正式工作**：完成阶段 0 缺项及冻结签核，再完成阶段 1 的 HDL 编译与 Testbench。保持九阶段顺序不变。
