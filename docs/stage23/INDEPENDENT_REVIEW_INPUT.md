# Linear xW IP — Stage 2/3 独立源码审查记录

**状态：REVIEW_NOT_ACCEPTED / EVIDENCE_INCOMPLETE**  
**审查对象：** 用户本轮上传的 `Stage_2_and_3.zip`  
**离线比较基线：** 此前上传的完整 `linear-xw-ip.zip`  
**Git HEAD（由离线仓库实际读取）：** `4f3fc68f1f59ab83ae2f657356eec35a41d56e22`

## 1. 文件与可读取性

两份 ZIP 均实际打开，并通过 ZIP CRC 测试。原始完整仓库含 184 个目录/文件条目，包括 `.git`、冻结标准、四个 Stage 1 RTL、Python 模型、Testbench 及脚本。新交付只含四个 `.v` 与三份 `.md`，另有目录条目。

**新增 RTL：**

- `xw_axis_bfp18_input.v`
- `xw_activation_buffer.v`
- `xw_ddr_addr_gen.v`
- `xw_weight_row_buffer.v`

它们全部不在原仓库的 `rtl/` 下；这次 ZIP 也没有提供已集成的 `rtl_sources.f` / `Makefile`。

原始离线仓库的 Python 测试实际重新运行：`test_stage1_contract.py` 23/23、`test_fp32.py` 10/10、`test_cycle.py` 2/2，合计 35/35 PASS。**没有运行新增 RTL 的真实 HDL 仿真：此审查环境没有安装 Icarus、ModelSim、Verilator 或 Yosys。**

## 2. 与冻结契约相符的主要设计

1. AXIS Parser 输入 512-bit TDATA / 64-bit TKEEP / 128-bit TUSER V2，28×signed18 元素/Beat，分 128 元素 Group；检查 Header、Sequence、Payload、Terminator，对应 `0x10`～`0x13`。
2. X Buffer 按每 8 个 Mantissa 存储为 144-bit Word；共享指数单独存储；尾 Word Mask 用 K 的余数计算。RAM 写、读位于无异步复位的时钟块，避免把大 RAM 全数组清零。
3. DDR Address Generator 用 64-bit 中间计算 Weight/Scale 整区间，使用 `RW=ceil(K/64)`、`RS=ceil(K/2048)`；实际请求步长 8、End 包含；提供分段 Offset。
4. Weight Row Buffer 存原始 512-bit DDR Word，按 8 字节粒度同步读出，尾 Lane 用 Mask 隔离。
5. 模块没有预先实现 B1/A2/Requant/AXIS Output；没有修改顶层 ABI 和冻结数值算法。
6. 缺 DDR 硬件 Timeout 的行为符合 V1.0 默认选择。真实 DDR 平台 Burst 上限仍需另行登记。

以上为**源代码结构和数学表达式审查**，并非 HDL 仿真通过的结论。

## 3. 必须解决的问题

### P0-01 — Activation Buffer 误用 `0x23` DDR_BUFFER 错误码

**证据：** `xw_activation_buffer.v` 第 72–76、129–134 行。模块对 `wr_word_index` 乱序、`wr_mask` 错误、`wr_last` 错误等 Parser→Activation 本地接口违例，返回 `8'h23`。

**冲突：** 冻结合同将 `0x23` 定义为 **DDR_BUFFER**（DDR 返回写入故障），而此模块存储的是来自 AXIS Parser 的 X，不是 DDR。此类内部握手/存储不变量错误应映射 `0x40 INTERNAL_FAULT`，真正非法 AXIS Beat 则应由 Parser 按 `0x10`～`0x13` 分类。不得误导系统状态码归因。

**要求：** 更正错误分类并用错误注入 TB 验证 Status 根因；不修改冻结错误码表。

### P0-02 — Addr Gen 的加载完成脉冲缺故障同时屏蔽

**证据：** `xw_ddr_addr_gen.v` 第 28、93、100、131–139、208–213 行。`load_done` 是寄存器脉冲，`blocked` 仅屏蔽 `load_ready`、命令等输出，没有屏蔽 `load_done`。

**可触发的静态时序反例：**

- 沿前：`state=S_LOADED`，`buffer_loaded=1`，`range_error=0`。
- 同一上升沿，DDR Receiver 看到 `ddr_rd_vld=1`、自身 `busy=0`、无请求，于沿后锁存无归属 Beat 的 `range_error=1`。
- Address Generator 在该上升沿根据沿前 `range_error=0` 和 `buffer_loaded=1` 将 `load_done<=1`。
- **沿后可能同时出现 `load_done=1` 与 `range_error=1`**；直到下一上升沿 Addr Gen 才锁定 `fault`。

这不一定意味着已有完整系统会错误推进，因为未交付的 Harness 可能额外阻断成功信号；但独立 Addr Gen 的完成事件缺少故障优先级保护，必须审查并修正。建议对公开完成信号进行故障组合屏蔽，并增加“错误与 Loaded 同沿”真实 HDL 测试。

### P1-03 — Parser Ready 与非法 `job_begin` 同周期的握手竞态

**证据：** `xw_axis_bfp18_input.v` 第 72–73、135–152 行。

当 `active=1`、`remaining=0`、`wr_valid=0`、`input_end=0` 时，`s_axis_tready=1`。若错误地在同一周期又断言 `job_begin=1` 且输入 Beat `s_axis_tvalid=1`，外部将看到成功 AXIS 握手，但 Parser 内部优先执行非法重复 `job_begin` 故障分支，不保存该 Beat。即**宣布握手但未消费数据**。

重复 `job_begin` 本身为非法控制，因此属于防御性协议问题，而非已证明的正常传输路径错误。建议 `s_axis_tready` 在 `job_begin` 冲突周期提前屏蔽，并新增定向测试。

### P1-04 — 无输出 Ready 的一拍 Buffer 读取，需要与阶段 4 明确对接

**证据：** `xw_activation_buffer.v` 第 20–25、64、145–149 行；`xw_weight_row_buffer.v` 第 16–20、50–59、127–132 行。

新设计采用 `rd_req` 发起、下一拍 `rd_valid` 脉冲，无 `rd_ready`；Work 先前的 Stage 2/3 实施说明曾提出 Response Ready/Hold。冻结合同并未强制内部接口必须配置 Ready，但消费者必须保证只能在可以接收时请求，不能把其当成具有输出反压的完整 Decoupled Handshake。

**要求：** 以接口文件明确该消费契约；若阶段 4 存在无法预测的计算 Stall，需要上层节流或增加保持寄存器，并同步精确周期模型。

## 4. 尚不能核验的项目（本轮 ZIP 未交付）

Work 的 `DELIVERY_REPORT.md` 声称完成 43/43 Python、16 组 HDL、678486 周期、Yosys RAM 结构检查、联合 Harness、软件 Golden 与事件 Trace。但当前 ZIP 缺少：

- `stage23_golden.py`, `stage23_model.py`, `test_stage23.py`
- `tb/support/xw_stage23_harness.v`，各模块 `tb/tb_xw_*_cycle.v`
- `tools/gen_stage23_tb.py`, `tools/run_stage23.py`, `run_stage23_tb.sh`
- `VERIFICATION_RESULTS.json`, `SYNTHESIS_RESULTS.json`, `FINAL_SOURCE_MANIFEST.json`
- `SOURCE_CHANGES.patch`, `logs/*`, `sim_build/stage23/` 的可再生说明
- 更新后的 `rtl_sources.f`、`Makefile`、集成入口

**结论：** 不能把“文档声称运行了”作为外部独立验收证据，也不能断言 Work 没在自己的工作空间生成这些文件；只是它们没有随**本轮附件**提供。

在缺少 Harness 时，尚无法验证：原四模块与新四模块的接线、Scale/Weight 分段 Offset 正确组合、最新 Stage1 Receiver 同周期首 Beat、最后 RAM Commit、System Fault 广播和错误首次优先级、非法 DDR 地址先于 AXIS 接收的实际门控。

## 5. 阶段状态

| 范围 | 代码存在 | 核心设计静态审查 | 新增 HDL 测试可复现 | 正式验收 |
|---|---|---|---|---|
| Stage 1 离线基线 | 是 | 已检查依赖 | 本轮未执行 HDL | 保留 Pending（不根据 Work 的自报 PASS 提升） |
| Stage 2 | 两个新 RTL 存在 | 主体合理；错误码和握手边界待修 | 否 | `REVIEW_NOT_ACCEPTED` |
| Stage 3 | 两个新 RTL 存在 | 地址/缓存主体合理；完成脉冲竞态待修 | 否 | `REVIEW_NOT_ACCEPTED` |
| Stage 2+3 联合 | Harness 未在附件 | 无法审查 | 否 | `EVIDENCE_MISSING` |
| Vivado 2023.2 | 未提供证明 | 不可推定 | 否 | `PENDING` |

## 6. 建议退回 Work 的最小修订任务

1. 完整输出此次 Work 任务中实际修改/新增的文件、脚本、Python 模型、全部 TB、联合 Harness、日志、源码 Manifest 和 Diff；不要只打包四个 RTL 与三份报告。
2. 对 P0-01、P0-02 进行源码修复，P1-03 增加防御性 Ready 屏蔽；P1-04 明确接口消费约束。保留冻结标准和旧 Stage1 数值 RTL 不变。
3. 增加 AXIS `job_begin`/TVALID 冲突、X 内部非法写入错误码、DDR Extra Beat 与 Buffer Loaded 同沿、以及 Reset/Abort/Loaded/Done 同沿的逐拍 RTL 测试。
4. 提供一组可复现命令和真实日志，并单独给出 Stage1 / Stage2 / Stage3 / 联合测试状态；无法运行的项必须继续 Pending。
5. 完成独立复测后，才能依据 `XW-DEV-STD-001 V1.0` 把相应阶段改为 PASS。不得基于自审报告直接声明签核。

---

**审查意见：** 这四个新模块不是需要整体推倒重来的代码；主要数据格式和地址计算路径具有合理基础。但当前交付中存在明确错误码分类问题、需要修复的完成/故障竞态，以及严重的验收证据缺失。建议修复与补交后再次独立审查，不建议以当前 ZIP 宣布 Stage2、Stage3 完成。
