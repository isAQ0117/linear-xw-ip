# Linear xW 阶段 1：四个 RTL 基础模块契约修复记录

**所属固定路线**：XW-DEV-STD-001 V1.0，阶段 1（验证已有四个 RTL）  
**技术契约**：XW-CONTRACT-STD-001 V1.0（已冻结）  
**实现状态**：`STAGE1_IMPLEMENTED_HDL_PENDING`（**不得写为 Stage 1 PASS**）  
**变更范围**：四个原有 `.v`、四份 TB、运行脚本、新增 Python 模块契约模型、B2 向量。无 AXIS Input/完整 Scheduler/顶层修改。

## 1. 源码权威性与版本关系

本工程以会话里实际可读取的原始 `linear_xw_fp32_cycle_rtl_v0_2.zip` 为输入；并与 `linear_xw_rtl_fp32_starter_v0_1.zip` 的四个 RTL 逐字节比对。由于此前曾交付的 FFN-style 两个 ZIP 当前没有实际可读取的副本，**本版本根据原代码恢复 ANSI 端口 / 分组注释风格**，不能宣称与当时 ZIP 或远程 GitHub `main` 逐字节一致。

- 四个 RTL 文件名、模块名、主数据端口、计算宽度和 DDR 六信号接口不变。
- 原 V0.2 的 Python 数值/架构模型及测试文件保留原内容；新加 `stage1_contract_model.py` 专门模拟基础模块实际寄存器行为。
- 已冻结的三份文档原样复制到 `docs/standards/`，不修改规则或改动九阶段路线。
- 对于 GitHub 中已经拥有 `docs/standards/` 的用户，合入本次 RTL 时不需要再次上传标准。

## 2. 各模块的具体变更

| 模块 | 保持不变 | 本次功能修改 | 内部端口变化 |
|---|---|---|---|
| `xw_job_dim_cfg` | 13 端口、静态忽略 `job_n/k`、动态 N/K 计算、17 位中间算式 | Verilog generate 编译/展开期拒绝非法参数组合；静态合法性由参数检查保证 | 无 |
| `xw_ddr_range_rx` | 六信号 DDR、512-bit、单 Outstanding、接收请求同拍首 Beat、响应无 Ready | 0x20/0x21 首故障锁定，reset/fault 时屏蔽请求，最终 Beat 后添加一拍下游交接保护；不可在下一命令清错 | 新增 `range_error_code[7:0]`，21→22 个端口 |
| `xw_scale_group_cache` | FP32 raw bits、512-bit Word、同步读请求、正常 Group 重装 | `load_begin/wr_valid/rd_req` 冲突变严重故障，清除 `loaded`、禁止错后读取、校验 MAX_K 对应的最大 K Blocks、17-bit ceil 中间结果；Group 正常切换不报错 | 新增 `cache_error_code[7:0]`，14→15 个端口 |
| `xw_fp32_scale_b2` | FP32 normal/subnormal、signed48×signed25→signed72、signed12 term exp | **没有修改任何 `assign` 算术表达式**；仅转换为 ANSI/功能分组注释，扩展 512 个边界与随机向量 | 无，6 端口 |

两个新端口仅为子模块输出，不属于冻结的 **35 个顶层物理端口**。后续统一故障状态由阶段 6/7 Job 控制和 Scheduler 实现，不应在阶段 1 提前把全局 Job FSM 塞入子模块。

## 3. 契约时序与适用边界

### 3.1 DDR Receiver

- `cmd_valid` 保持稳定直到 `cmd_ready` 握手；当 DDR Ready 无效时合法命令应等待，不应报故障。
- `ddr_rd_req = cmd_valid && cmd_ready`，必须在非 Reset、非 Fatal、非 Busy、非 `handoff_hold` 下成立。所有请求仍是单拍 FFN 兼容握手。
- 允许在请求接受上升沿 t 同时观察到第一个 `ddr_rd_vld=1`；`word_valid` 在 t 后随寄存器可见。
- 最后一个有效 Beat 的上升沿 t 后，`word_valid=1`、`range_done=1`、`handoff_hold=1`；t+1 由下游同步存储提交；下一请求最早在 t+2 上升沿被接受。
- 无归属 DDR Beat（含最后 Beat 之后的额外 Beat）→ `0x21`；格式非法的新命令 → `0x20`。**首次错误锁定，只有受控 Reset 清除**；故障期间不再输出 `word_valid`、`ddr_rd_req`。
- 物理接口缺少 Response ID/Last/Ready，因此无法识别所有 DDR 错误；旧响应清理仍为外部系统义务。无硬件超时（冻结标准的默认选择）。

### 3.2 Scale Group Cache

- `load_begin` 在时钟沿 t 锁存 Group 配置；`wr_valid` 最早从 t+1 上升沿开始接受。若在同沿重叠，则锁定 `0x40`，不能无提示丢第一拍数据。
- 正常新 Group 的 `load_begin` 会使 `loaded=0`，随后重新装载；**但不能**在 `cache_error=1` 时解除故障。
- `wr_word_index` 必须从零连续增加且不超过 `expected_words`；额外/乱序写入锁定 `0x23`。
- 读请求仅允许在完整装载成功、索引合法、未锁定错误时被接受，数据按同步读有效脉冲送出。无效读、并发读写、配置/数据重叠为 `0x40`。
- RAM 存储位不在 Reset 时逐个清空，以避免不必要的片上 RAM 资源开销；仅有效控制状态清零。
- 后续阶段若换成真实同步 BRAM，应单独记录精确读延迟并同步更新软件模型和 TB，不应在本阶段擅自调度并行读写。

### 3.3 B2 错误传播

`scale_valid=0` 时，B2 的零 Term 只是无效占位。未来 A2 消费控制器必须阻止此 Term 提交，并映射 `INVALID_SCALE=0x30`；本轮不增加 B2 的时钟或握手端口。

## 4. 本次验证项目

- `./run_stage1_software.sh`：保留 12 项 FP32 软件回归 + 新增 23 项 Stage-1 独立模块状态和交接测试 = 35/35（见报告中的实测记录）。
- `python3 tools/gen_b2_vectors.py --check`：保证固定的 512 个 signed72/FP32 bit-exact 向量可以重生。
- `python3 tools/check_stage1_static.py`：结构检查；若加 `--baseline path/to/original/rtl`，会进一步比较 B2 的所有赋值表达式是否完全一致。
- `./run_rtl_tb.sh`：Icarus 四模块 RTL Testbench 与两项非法参数编译/展开期反例。脚本在编译失败、仿真失败、出现 FAIL、缺少/重复 PASS 时一律返回非零。
- `./run_modelsim_tb.sh`：ModelSim/Questa 等价四模块与两项参数反例入口。
- **未执行 HDL 编译/仿真**：当前环境无 Icarus、ModelSim、Verilator 或 Vivado 仿真器；软件和结构检查不能代替实际 HDL 验证。

## 5. 不在本阶段修改的内容

- 顶层 ABI 35 端口、Job/Status 的完整全局控制、DDR Layout V3、B3-B-FP32 Numeric Profile、A2/Requant 规则。
- 新的 DDR 地址生成、AXIS Input、Weight Buffer、Scheduler、多 Batch 复用（依旧按固定九阶段推进）。
- FP32 Scale B2 的计算公式与精度，没有增加流水级。

## 6. 正式 Stage-1 退出条件（尚待完成）

1. 在目标 HDL 工具上运行四份 TB，编译/模拟全部 PASS，存档工具版本和日志。
2. 按契约覆盖非法参数展开失败、Reset 后外部事务清理、合法 Response 空隙和非法 Extra Beat 场景。
3. 核对 Python 模块模型与 RTL 同一输入轨迹的实际事件周期，不能把“Python 单独通过”等同于已完成 RTL Lockstep。
4. 将新的子模块内部错误码输出与未来控制器映射契约纳入接口集成文档。

**验收状态：`PENDING_REAL_HDL`。**
