# Linear xW IP Stage 4 完整交付报告

当前阶段4；子任务：B1→B2→A2局部核心、独立数值验证、实际HDL、周期/资源测量和交付。**本地验收PASS（本文范围）；外部独立复审/正式签核PENDING。** 依据XW-DEV-STD-001 V1.0 / XW-CONTRACT-STD-001 V1.0及上传RTL House Style，无冻结契约变更。Stage5/6/7/8没有提前实现。

## 可确认的完成状态

| 项目 | 实际状态 | 证据 |
|---|---|---|
| 四个Stage4生产RTL | 已实现，纯Verilog2001；Icarus和Yosys可处理 | rtl/下B1/B2 Pipe/A2/Compute Ctrl |
| Level1A既有numeric | 保持上传原字节，继续作冻结Golden | UPLOADED_BASELINE.json / AUDIT_RESULTS.json |
| Level1B独立数学Golden | PASS；Fraction、独立FP8/FP32、区间搜索RNE | stage4_golden.py / numeric与模块日志 |
| A2精确分段原型与证明 | PASS（推导+有限向量）；不是形式化穷举 | A2_PROOF.md / stage4_a2_math.py |
| Level2实际微架构周期模型 | PASS；逐寄存器/FSM/FIFO/真实一拍缓存组合 | stage4_model.py / stage4_integration.py |
| Level3真实RTL仿真 | **PASS，Icarus11.0，-g2001 -Wall** | VERIFICATION_RESULTS.json / logs/ |
| PRE/NBA周期一致性 | **PASS，252859拍，逐拍完整输出比较** | 五份向量、五份自检查TB与日志 |
| 实际事件/数据一致性 | **PASS，21299条合法事件，含903个B1/B2/A2数值检查点** | compute_rtl_events.jsonl / check_events |
| 通用综合结构 | PASS，Yosys0.23；无latch、无组合环、无check问题 | SYNTHESIS_RESULTS.json / logs/*synthesis.log |
| xc7 family资源探索 | PASS，完整映射且无残留通用FF | XC7_MAPPING.json / xc7_mapping.log |
| Vivado2023.2实际综合、布局布线及时序 | **PENDING，未安装/未运行** | tools/vivado_stage4.tcl为可执行入口，不是执行证据 |
| 目标器件、100–150MHz、上板/真实DDR | **PENDING** | 未提供part/平台约束；不宣称时序收敛 |

## 源码基线与修改边界

附件实际HEAD为`b67698ac6d318518ae328ab3ae91496f5a55b039`，122个tracked文件，Git fsck成功。上传20个modified仅CRLF/LF，无内容差异。以**上传工作树bytes**为基线，未从旧版重建、未checkout旧代码、未commit/push/merge/PR。两ZIP CRC和SHA见REPOSITORY_AUDIT.md。

全部8个旧生产RTL、全部5个standards文件及numeric.py共14个保护文件逐字节未变。原43项软件和Stage1/23实际HDL在独立基线副本重跑通过；Stage23为16组678659拍，另有原四TB、参数反例、手写审查和2个P0 mutation。当前重跑日志在logs/baseline/，不拿上传的历史PASS冒充此次执行。旧历史文档保持来源；本报告覆盖新增Stage4状态。

改动仅为四个生产RTL及本阶段模型/TB/工具/数据/文档，另更新Makefile、rtl_sources.f、README与当前状态说明。完整差异SOURCE_CHANGES.patch相对上传的实际bytes，最终完整清单/哈希在DELIVERY_MANIFEST.json。原始Git历史由用户附件保有，交付工程包不另造历史。

## 设计与最高风险算术

B1采用8×signed18×signed19，乘积37bit、pair38bit、half39bit、slice40bit、Block48bit。输入可以连续16拍；最后Slice后4个沿间隔产生RAW，整体20cycles。Tag/exp/last同级移位，mask屏蔽的FP8 padding不检查NaN。发现有效7F/FF报告31并排空，不输出RAW。

B2两级弹性包装直接例化原xw_fp32_scale_b2，输入锁存和乘积/指数输出寄存；normal/subnormal保持完整signed72/signed12，非法Scale为30。提前Scale读取也复用原模块的scale_valid，不另建数值解码器。

A2保持有序每Block一次RNE。差值≤48或旧state零使用signed128精确运算；特殊路径按64bit逐段从低到高传播carry/borrow。只保存精确结果最高两段及以下完整非零判定，低段先完成加减，因此巨大gap中的细小项和借位均不会被提前丢弃。负2幂边界、正负tie、重舍入均由证明与定向向量覆盖。

合法核心term exponent[-286,222]、term幅度<2^66，512个Block下state exponent保守界[-286,251]，gap≤537，完整精确对齐610bit上界足够。实际不创建610bit寄存器/移位器，最多10个64bit段。额外支持全部字段指数范围，最大34815差值/546段，独立手写RTL测试也执行；其耗时不属于合法核心64cycle目标。ACC_RANGE对合法本配置数学上不可达，用受控状态注入验证32传播，不冒充自然业务覆盖。

指定反例：旧(1,0)+新(1,-286)实际返回(70368744177664,-46)。另加入高72bit项恰好half-way、远处旧state打破tie的正负向量，并用删除remote sticky的RTL突变确认测试能抓住错误。

Controller只管理一个已缓存Channel：Loaded检查、Scale提前读、K Block升序、8lane Slice、253×4完整响应FIFO、B1/B2/A2握手、提交后下一Block、结果保持。FIFO计入pending，实际满载4且reserved最大4；RAM没有ready，不改旧接口。Stage23完整Harness的预检查/Parser/AddressGen/Receiver/真实缓存全部参加联合验证，未实现全局Scheduler。

## 验证范围与实测数量

| 套件 | 实际覆盖 | 比较周期 |
|---|---|---:|
| B1 | 931 Block；所有256 FP8编码；18bit两端；零/正/负/混合；尾mask、非法/abort/reset/连续16slice | 19976 |
| B2 | 5075向量；FP32 normal/subnormal、极值、±0/负/Inf/NaN；RAW正负边界；随机反压与abort | 8014 |
| A2 | 6894对旧state/term案例；13585次实际更新；419次round retry；边界/抵消/非结合/快特切换 | 146790 |
| Controller独立 | 33通道；满FIFO/长stall；11类故障；首错优先/Loaded/Mask/响应/abort/reset | 21482 |
| Stage234联合 | 15合法通道；N2K129四更新；长序列；231 DDR请求/636 beats；数值错误3类、在途故障3类 | 56597 |

K矩阵：1、7、8、9、127、128、129、2048、2049、4096、12288。联合常规路径覆盖全矩阵，大指数路径覆盖4096/12288，独立Controller另覆盖全矩阵特殊/随机stall。N=2K129的两通道共四个Block逐个RAW/Term/pair比较。

Stage4软件5个unittest方法内部包含13894组A2三方比对、所有FP8及5010个FP32码，另有上述生成刺激的独立逐Block scoreboards。独立数学Golden不导入生产三个数值函数；Cycle Model不使用旧cycle_model的latency参数。PRE与NBA都比较，X/W/Scale仍按旧寄存器模型的真实一拍返回组合。

手写tb_xw_stage4_review独立验证：注入ACC_RANGE→32且无result，后续21不覆盖首码但升级lock；全signed16/signed12指数极限；已发布正确结果在late fault/反压时不变；发布前fatal阻止A2/result。另2个非法MAX_K必须在命名guard处展开失败。

4个故意错误的临时RTL均被实际HDL TB拒绝：masked NaN误检查、负边界错误、远处sticky丢失、FIFO不计在途。日志中的这些FAIL是**预期反向实验**，最终生产RTL套件没有FAIL。不要把mutations/下源码当生产文件编译。

## 来自实际HDL事件的性能

计数均包含起止采样沿。Block：首RAM_READ→A2_UPDATE；Channel：COMPUTE_ACCEPT→首次RESULT_VALID。输出发布事件用NBA产生沿，握手另记。统计由report_stage4_performance.py读取实际$fdisplay JSONL，21299条事件另与模型逐条匹配；不由任意latency参数推算。

| 完整128元素Block，无stall | 常规（227个样本） | 大指数差（64个样本） |
|---|---:|---:|
| B1接受间隔 | 1 | 1 |
| B1，首Slice→RAW | 20 | 20 |
| B2，接受RAW→TERM | 2 | 2 |
| A2，接受TERM→提交 | 8 | 16 |
| 首RAM读→A2提交 | **32** | **40** |
| 下一Block启动间隔 | **33** | **41** |

A2独立案例中常规零Term2cycle、非零8cycle、retry10cycle；特殊路径8..28cycle，包含超出真实核心exponent范围的随机接口测试。合法核心最多10段，理论特殊上界为18cycle（含retry），由此Block上界42cycle；这是结构推导，不称本次所有合法输入穷举实测。

| K | 常规Channel计算周期 | 大指数差混合Channel周期 |
|---:|---:|---:|
| 1 / 7 / 8 | 19 | — |
| 9 | 20 | — |
| 127 / 128 | 34 | — |
| 129 | 52（N2两个通道各52） | — |
| 2048 | 529 | — |
| 2049 | 547 | — |
| 4096 | 1057 | 1185 |
| 12288 | 3169 | 3553 |

以上不含先前AXIS/DDR加载、也不含结果等待。每个联合Channel另外测试17个result stall采样沿，RESULT_VALID→ACCEPT相隔18沿（1个正常最早握手沿+17个stall）。K129人为FIFO消费stall案例81cycle，另列，不混进32cycle结论。

Controller开销：首读前1沿设置；RAM/FIFO使B1比首读晚2沿；A2提交后Controller下一沿观察并设置下一Block，再下一沿发首读，Block间有1个控制观察沿。没有等待乘法树而人为插入Slice空拍。FIFO从满载恢复按保守credit规则可多1拍空隙；第一版不跨Block投机，不声称达到32cycle启动间隔。

## 资源与时序的准确边界

Yosys0.23通用前端对四新模块check -assert为0问题，无latch、无组合环；B1恰好8个乘法器，A2无乘法器/超宽RAM；FIFO253×4。旧X/W同步RAM另用原结构检查在本轮工具上重跑成功。数组替换寄存器的告警仅是短B1寄存器数组，属于有意结构。

xc7 family探索性映射：**14 DSP48E1、6928 LUT、2459 FF、43 RAM32M、0 BRAM**（只统计计算Core，不包含外部X/W/Scale缓存）。其中B1用8个DSP，原B2保守映射6个DSP；不把6DSP当Vivado最优资源。没有128路全展开乘法。

组合拓扑最长路径47个技术单元，来自A2特殊路径提取/65bit运算/前导检测控制；这不是47ns，也不是实际关键时序延迟。为控制该链，已经将高项offset在SETUP寄存、移位量缩到合法6/7bit、单1检测改为分字节。未改变算术或周期。Vivado可能进一步打包DSP/优化carry，也可能需要额外流水；**没有器件、布线和约束依据，100/150/200MHz均不宣称达标**。建议先用提供的tcl对实际part尝试10ns或6.667ns，再依据真实路径优化。

## 复现入口与交付内容

仓库根执行：

```sh
python3 tools/check_stage4_delivery.py  # 先核验交付快照
make py-test
make rtl-test
make stage23-test
make stage4-test
make stage4-synthesis-check
python3 tools/map_stage4_xc7.py             # 另需yosys-abc或berkeley-abc
python3 tools/audit_stage4.py
```

`make all-tests`包含原三个测试target及Stage4实际HDL。Stage4生成器检查、数值测试、五个模型/TB、手写审查、参数反例、mutation与实际性能提取都由run_stage4_tb.sh执行，任何意外FAIL/缺PASS/重复PASS/编译错误均非零退出。ModelSim/Questa原脚本保留，但本轮没有运行；Icarus通过不写成ModelSim通过。

Linux amd64受限环境可选：`python3 tools/bootstrap_stage4_hdl.py --with-yosys`，按它输出的export PATH命令设置环境。工具只安装到sim_build/toolchain，包哈希固定，不改系统；本轮实际测试了此入口。普通已有HDL环境无需bootstrap。

全部生产源码、独立Golden/周期模型、TB/Harness、Skill检查器副本、生成/运行工具、五套实际vec/vvp、综合JSON网表、日志/事件/测量、源码差异和最终哈希都在完整工程包。大部分sim_build均可重生；工具二进制/下载缓存不作为工程依赖打包。看REVIEW_STAGE4.md快速定位，PORT_REFERENCE.md查看逐端口列表。

## 保留限制

1. 仅M1/P_N1/P_K8、一个Channel/Block在途；外层负责X/Weight/Scale缓存所有权与req_k一致、装载和作废。三个Loaded无法反查Job/channel标签。数值错误后本核等待干净边界的受控reset，不自动重试。
2. 计算result不是最终BFP18张量或Job成功Status；Stage5 Requant、Stage6 AXIS/Status、Stage7 Scheduler和多Batch没有实现。
3. slice_enable/响应FIFO是内部流控接口，不改变旧RAM端口；不支持任意可变延迟RAM。缺失、错位响应按40，不以硬件无限等待假装正确。
4. 极端全字段A2测试可超过64cycles；真实核心合法边界最多10段。有限随机/定向验证及推导不等于形式化穷举证明。
5. Vivado2023.2编译/综合/实现/时序、具体FPGA/BRAM布局、CDC和上板均Pending。generic check和family mapping不替代这些。
6. 外部DDR最大burst/延迟/旧响应清理仍待平台登记；测试burst3不是硬件平台承诺。无ID/Last无法检测全部错归属，不宣称自动恢复。
7. 最终自审见DESIGN_SELF_REVIEW.md；这是重新从合同/公式/边沿/容量出发的内部独立自审，没有冒充外部审查签核。
