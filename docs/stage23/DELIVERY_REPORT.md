# Linear xW IP Stage 2+3 联合交付报告

当前阶段：2、3；当前子任务：完成实现、真实仿真、设计自审与交付归档。本地测试：**PASS（本文限定的M=1输入与DDR缓存范围）**；**独立复审/正式签核PENDING**。固定路线 XW-DEV-STD-001 V1.0；技术合同 XW-CONTRACT-STD-001 V1.0；无外部契约变更。Stage4–8不在本轮实现范围。

本报告已纳入独立审查R1修订，逐项处理见[REVIEW_RESOLUTION.md](REVIEW_RESOLUTION.md)。新增独立手写定向TB `tb/tb_xw_stage23_review.v` 及日志 `logs/review_directed_hdl.log`。

## 有效版本与工作目录

实际工作目录：`/workspace/scratch/5f8e1b5d92cf/linear-xw-ip`。
在线默认分支 `main`，开发基线 HEAD `4f3fc68f1f59ab83ae2f657356eec35a41d56e22`。附件ZIP的50个文件与在线tracked文件全部逐字节一致；ZIP没有`.git`/历史，Git历史来自真实在线clone。已逐文件读取并核对，详见 [REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md) 和 [BASELINE_FILES.json](BASELINE_FILES.json)。

原四个Stage1 RTL已经包含修订，本轮保持它们字节不变。新代码在此checkout工作目录中，未自动commit、push、merge或创建PR。冻结标准文件均保持原始SHA256。

## 状态必须分开理解

| 范围 | 已实现 | 软件测试 | 真实HDL测试 | 验收口径 |
|---|---|---|---|---|
| Stage1四基础模块 | 已有Stage1修订，已确认 | 原35项通过 | 四原TB、2参数反例、RX/Cache新逐周期通过 | 模块验收PASS，补齐原HDL Pending |
| Stage2 Parser + X Buffer | 完整M=1输入、28→8、独立指数/尾mask | 独立data Golden + 寄存器周期模型通过 | Parser108822拍、X28146拍逐沿通过 | Stage2 PASS（M=1） |
| Stage3 Addr + W Buffer + 复用RX/Cache | 全布局预检查、物理分段、完整逻辑写入、8-lane读 | 地址/原始bits/周期模型通过 | 地址5种Burst、W12758拍逐沿通过 | Stage3 PASS（缓存范围） |
| Stage2+3联合Harness | 已接通X/Scale/Weight；实际预检查门控 | 全行/全组raw bits和周期一致 | 五种Burst联合 + 静态尺寸通过 | 联合缓存测试PASS；不是完整Linear端到端 |
| 泛化结构检查 | 同步RAM、无阵列复位 | — | Yosys四新模块0问题、无latch | 仅generic结构PASS |
| Vivado2023.2、FPGA实现/时序/上板 | 未执行 | — | **PENDING** | 不宣称目标实现PASS |
| 真实DDR平台规格/旧响应清理 | 未取得 | — | **PENDING** | 部署前必须登记 |
| Stage4–8 | 未实现 | 历史原型保留 | 未验证 | NOT_STARTED |

Stage1旧报告及冻结文档中的Pending是历史快照；本轮真实HDL证据在logs/stage1_hdl.log，不将冻结规则签核误称工程通过。

## 交付文件与接口

以下路径均相对上述实际工作目录；所有内容保留在环境中。

| 类别 | 文件 |
|---|---|
| Stage2 RTL | `rtl/xw_axis_bfp18_input.v`、`rtl/xw_activation_buffer.v` |
| Stage3 RTL | `rtl/xw_ddr_addr_gen.v`、`rtl/xw_weight_row_buffer.v` |
| 测试Harness | `tb/support/xw_stage23_harness.v` |
| 独立数据级Golden | `stage23_golden.py` |
| 寄存器/状态机/RAM周期模型 | `stage23_model.py`，复用 `stage1_contract_model.py` |
| 软件功能、边界、随机、异常测试/轨迹源 | `test_stage23.py` |
| 自检查Verilog TB | `tb/tb_xw_axis_bfp18_input_cycle.v`、`tb/tb_xw_activation_buffer_cycle.v`、`tb/tb_xw_weight_row_buffer_cycle.v`、`tb/tb_xw_ddr_addr_gen_cycle.v`、`tb/tb_xw_stage23_harness_cycle.v`、`tb/tb_xw_ddr_range_rx_cycle.v`、`tb/tb_xw_scale_group_cache_cycle.v` |
| 参数反例 | `tb/negative/tb_xw_invalid_stage23_params.v`，保留原2项Stage1反例 |
| 工具与复现 | `tools/gen_stage23_tb.py`、`tools/run_stage23.py`、`tools/check_stage23_synthesis.py`、`run_stage23_tb.sh`、`Makefile`、`rtl_sources.f` |
| 接口/FSM/RAM/复位/错误设计 | [INTERFACE_AND_TIMING.md](INTERFACE_AND_TIMING.md)、[PORT_REFERENCE.md](PORT_REFERENCE.md) |
| 独立设计自审 | [DESIGN_SELF_REVIEW.md](DESIGN_SELF_REVIEW.md) |
| 机器可读结果 | [VERIFICATION_RESULTS.json](VERIFICATION_RESULTS.json)、[SYNTHESIS_RESULTS.json](SYNTHESIS_RESULTS.json) |
| 全部新增/修改文件差异 | [SOURCE_CHANGES.patch](SOURCE_CHANGES.patch)（可用git apply --check验证） |
| 最终交付哈希 | [FINAL_SOURCE_MANIFEST.json](FINAL_SOURCE_MANIFEST.json) |

接口设计在编写RTL前已完成。主要实现选择：Parser每拍解包一个Mantissa，144bit pack跨28元素Beat保存残留；完整X为144bit同步RAM，指数独立；W完整512bit写入以接住无Ready连续返回，B1方向每拍读8个byte。RAM拆成无复位时序块后仍为一拍读。读写/配置并发明确报40，不依赖RAM同址读写模式。

逻辑Group/Row各INIT一次；物理segment的word_index加稳定offset形成连续逻辑index。最后物理Beat在Receiver寄存后下一沿才提交RAM，Address Gen保留COMMIT隔离沿，然后等待Loaded再发load_done。Harness在完整Job地址检查成功之前不开放AXIS ready，拒绝非法地址是实际硬件行为。

## 独立性与实际验证结果

软件完整回归：**43/43 PASS**（原35项 + 新8个测试方法；方法内包含全部边界矩阵、定向异常和固定种子随机场景），日志 [logs/final_software.log](logs/final_software.log)。B2固定512向量和7份生成TB均可再现。

真实HDL：**Icarus Verilog 12.0**，全部以 `-g2001 -Wall` 编译；16组逐沿轨迹，另加独立手写审查TB和两项P0反向突变检查，总计 **678659个时钟周期**，每拍分别比较沿前组合输出与NBA后全部模块输出。额外新6项非法参数展开必须在指定XW_INVALID保护处失败，原Stage1还有2项。执行/缺失/重复PASS/FAIL检查均fail-closed；软件成功不替代HDL成功。

| 真实周期测试 | 周期数 |
|---|---:|
| Parser | 108822 |
| Activation Buffer | 28146 |
| Weight Buffer | 12758 |
| Addr Burst1 / 2 / 3 / 64 / 192 | 63091 / 32147 / 21647 / 1827 / 1192 |
| Harness Burst1 / 2 / 3 / 64 / 192 | 90664 / 82986 / 80260 / 76219 / 76284 |
| Harness静态模式 | 250 |
| Stage1 RX / Scale周期补验 | 1115 / 1251 |

软件Golden未调用周期模型：AXIS输入按逐bit构造、TUSER按little-endian字节构造；X期待Word用独立二进制字符串拼接并含硬编码已知向量；DDR Golden先按byte坐标建立半开区间再换算地址，物理Range独立枚举后分组。Weight期待来自原始bytes、Scale期待来自原始uint32，不使用读缓存后的数据反算预期。它们与逐寄存器模型、Verilog实际输出形成三方交叉检查。

实际RTL事件：Burst3 Harness从TB的实际采样信号/内部寄存器 `$fdisplay` 输出 **17469条**，见 [logs/harness_rtl_events.jsonl](logs/harness_rtl_events.jsonl)。其中 **8822个外部事件** 的周期与Job归属重新从输入/预期接口记录独立重建比较，全部相同；另检查实际INIT每逻辑对象一次、BUFFER_WRITE逻辑index连续。日志不是Python冒充RTL trace。共1966次实际请求，包括最后一笔刻意不给返回的请求；VERIFICATION_RESULTS.coverage.requests为DDRDriver记录的1965次正常驱动请求，故障/缺返回手动注入另列在实际事件中。

重点矩阵已覆盖：

- K=127/128/129、2048/2049，另含1/7/8/27/28/29/63/64/65/4096/12288；独立模块扩到K65535。联合Harness容量MAX_K12288，未声称联合K65535通过。
- N=127/128/129完整通道访问；Scale跨第16/17值、跨N Group，读原FP32包含subnormal/normal/非BF16精度bits。
- Burst=1/2/3/64/192；同周期首Beat、连续返回、随机Gap、DDR request ready stall。Burst192在联合K12288为完整192-beat Row；大于192的实际分段另在K65535地址模块测试。
- AXIS任意合法输入间隙、保持Beat等待ready、Parser输出随机stall及长stall、跨Beat残留、指数变化和尾mask。错误码10/11/12/13全部字段类别；尾beat字节内padding和高bit、keep holes/highbit；错误优先级/首错sticky/Reset。
- DDR全区间重叠、不对齐、溢出、2^29独占边界合法、Start/End=2^29-8实际请求；非法地址时AXIS始终不握手；拒绝后允许新配置。
- 已Loaded Row后的额外DDR Beat立即撤销公开缓存有效性；AXIS10与DDR21同沿首错选择10；内部提前读40；idle无归属Beat不伪造result；故障后禁止旧缓存有效读、禁止新Job。
- 在途DDR无返回等待40拍不启动未获平台授权的timeout；外部清理后reset；未清理的旧响应在idle到来会锁定。无法识别所有错归属数据的限制保留。

各原始编译/运行日志见 `logs/*_hdl.log`、`logs/stage23_regression.log`、`logs/stage23_negative_elaboration.log`。实际向量和vvp保留于被Git忽略的 `sim_build/stage23/`，运行器可完全重建；向量SHA256逐组记录，未强制打包。

## 设计自审与综合结构证据

自审发现首版RAM在异步reset控制块中会被Yosys展开寄存器，已拆为真正无复位同步RAM访问，保留一拍读契约并重新跑全部RTL。最终Yosys0.33 `proc; opt; memory_dff; memory_collect; opt_clean; check -assert` 四新模块均0问题、无latch。MAX_K12288下X数据144×1536、指数8×96、W512×192，均1同步写口/1同步读口，memory_dff确认读FF合并。

`logs/*_memory_initial.log` 为自审时失败/中断的历史观察，不是最终结果；最终凭 `SYNTHESIS_RESULTS.json` 与 `logs/xw_*_synthesis.log`。Yosys运行环境无procfs，为定位自身share目录使用仅返回已知二进制路径的本地readlink兼容shim；不修改RTL或综合语义。此为泛化结构检查，未使用它替代Vivado2023.2、器件映射或timing signoff。

## 可复现命令

标准工具在PATH中时，从仓库根执行：

```sh
make py-test
make rtl-test
make stage23-test
make synthesis-check
```

所需Python3仅标准库；真实HDL依赖iverilog/vvp12.0；可选结构检查依赖yosys0.33。原ModelSim脚本保留，但**本轮未执行ModelSim或Vivado**。

本环境的解包工具位于 `/workspace/scratch/5f8e1b5d92cf/toolchain/bin`；若在同一受限环境复现：

```sh
export PATH=/workspace/scratch/5f8e1b5d92cf/toolchain/bin:$PATH
export TMPDIR=/workspace/scratch/5f8e1b5d92cf/toolchain/tmp
make py-test
make rtl-test
make stage23-test
make synthesis-check
```

## 保留的限制和未验证项

1. 仅M=1、P_N=1、P_K=8、单Outstanding、完整X/Weight Row、DDR与计算不重叠；串行Parser性能不是每拍一AXIS Beat。
2. Harness只验证缓存控制，没有完整Scheduler、B1/A2、Requant、输出、顶层Job Status；其result表示缓存测试结束，不能作为Stage7端到端成功Status。
3. W/Scale模块搬运原始bits；FP8 NaN/非法Scale数值异常由未来Stage4消费检查，不声称本轮完成计算异常路径。
4. DDR_MAX_BURST_BEATS默认0强制显式选择；测试1/2/3/64/192不代表真实控制器规格。响应最大等待/Gap和旧响应清理能力仍待平台登记。无自动timeout或故障后自动恢复。
5. rst_n在子模块为已经同步释放的本地复位；Harness统一两级释放同步。部署时须保持共同复位域，且外部DDR/AXIS先清理。无ID/Last无法检测所有丢失/额外/错归属组合。
6. Vivado2023.2编译/综合/器件BRAM映射、资源/时序/CDC/上板/真实DDR控制器未验证。泛化综合结构和有限随机仿真均不是形式化穷举证明。

最终独立自审详见 [DESIGN_SELF_REVIEW.md](DESIGN_SELF_REVIEW.md)。在已列验证范围内无已知未解决Stage2/3功能缺陷；成果保留供后续独立审查，不扩张验收结论。
