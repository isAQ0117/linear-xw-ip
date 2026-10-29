# Linear xW IP Stage5 完整交付报告

当前阶段5，Step5.0–5.6已完成；本地实现与验证PASS，外部独立验收Pending。依据XW-DEV-STD-001 V1.0、XW-CONTRACT-STD-001 V1.0和附件Verilog RTL House Style，无冻结契约变更。

## 最终状态

| 项目 | 状态 | 实际证据 |
|---|---|---|
| RTL Implemented | PASS | 4个新增生产RTL，纯Verilog2001 |
| Numeric Golden | PASS | 5192组两Golden/有界原型；262144个signed18输入穷举 |
| Python Cycle Model | PASS | 真实FSM、pending、同步RAM、retry、pack及提交，无人为latency |
| HDL Module Simulation | PASS | Icarus11.0，模块PRE/NBA全输出比较及手写常量TB |
| Stage4+5 Integration | PASS | N2/K129、N129/K129、N129/K1，真实旧RTL和缓存路径 |
| Synthesis Structure | PASS | Yosys0.23同步RAM/零latch/零组合环；xc7家族探索映射 |
| Vivado Timing | **Pending** | 无Vivado2023.2、实际part和系统约束，未宣称100–150MHz达标 |
| Remaining Risks | 明确保留 | 外部干净边界/复位释放、实际器件时序、外部独立签核 |

## 交付索引

- RTL：rtl/xw_output_group_buffer.v、xw_bfp18_requant.v、xw_result_buffer.v、xw_stage5_ctrl.v。
- 数值：stage5_golden.py（独立Fraction，不导入numeric）、test_stage5_numeric.py；NUMERIC_DECISIONS.jsonl.gz含输入、最终结果、retry、错误和每个RNE的floor/余数/分母指数/tie/进位。
- 周期/刺激：stage5_model.py、test_stage5.py、stage5_integration.py。
- TB：四模块及Stage45 Harness各一份cycle自检TB，另tb_xw_stage5_review.v独立手写常量检查；tb/support/xw_stage45_harness.v直接连接真实Stage234。
- 运行：run_stage5_tb.sh、tools/run_stage5_all.py、run_stage5.py、run_stage5_review.py、gen_stage5_tb.py。
- 接口/证明：REPOSITORY_AUDIT.md、INTERFACE_AND_TIMING.md、PORT_REFERENCE.md、NUMERIC_PROOF.md、STAGE6_READ_INTERFACE.md。
- 实测：VERIFICATION_RESULTS.json、REVIEW_RESULTS.json、INTEGRATION_MEASUREMENTS.json、READBACK_RESULTS.json、PERFORMANCE.json、SYNTHESIS_RESULTS.json、XC7_MAPPING.json、ENVIRONMENT.json及logs/。
- 审查/差异：DESIGN_SELF_REVIEW.md、SOURCE_CHANGES.patch、DELIVERY_MANIFEST.json。Manifest覆盖完整交付文件，排除自身以避免循环哈希；sim_build/stage5保留实际vec和综合JSON。

## 基线与实现边界

上传HEAD为a6010b91105164b139afcc7324e17e205b09ef63，175个工作树文件；初始20项差异仅CRLF/LF。旧12个生产RTL、numeric及5个标准共18项保护字节未变。Git fsck与ZIP CRC通过；旧历史材料缺失/HEAD差异/行尾签名问题见审计，不悄悄回退历史。

原43项软件测试通过；原Stage1四模块、Stage23的678659拍、Stage4的252859拍及原定向/突变测试已在本轮实际重跑。日志复制到stage5/logs/baseline_*，不以历史PASS代替。第一次原脚本因环境缺/tmp停止，设置TMPDIR后全套HDL通过；保留两次日志。

Stage5只负责M1、P_N1、顺序通道和整Job结果。MAX_N默认12288，可参数化1..65535，合法动态N包含尾Group。无AXIS sender、TUSER生成、全局Scheduler、最终Job Success Status或多Batch。测试层显式逐通道加载/计算，不冒充Stage7。

## 数值、RAM与提交

接收时写128×64原始State并计算signed18 Hmax，没有额外扫描。候选H−16与原H−17起搜严格等价，最多一次重试；retry从原State重新RNE。幅度无符号48bit容纳MIN，移位分类后仅使用18/48bit有界数据通路；临时signed19容纳±131072，对称上限131071。最终指数确定后才检查signed8。指定(262143,-130)→(65536,-128)及正负double-rounding反例均经真实RTL检查。

Result Mantissa为144×ceil(MAX_N/8)，Exponent为8×ceil(MAX_N/128)。默认逻辑容量27744Byte，另临时Group1024Byte。地址16g+s，lane低位优先，尾lane真实置0。投机attempt允许写入但不commit；Buffer还记录18'h20000并禁止其最终提交。最后word真实写入后再提交指数/有效前缀。所有Group完成后才publish整Job，并开放一拍同步读。失败/abort/reset只作废元数据，不清RAM。

## 实际验证

| 套件 | 结果 | 周期 | 覆盖概要 |
|---|---|---:|---|
| group | PASS | 3123 | {'groups': 32, 'lengths': [1, 7, 8, 9, 28, 29, 127, 128], 'fault_cases': 7, 'seed': '0x5181'} |
| requant | PASS | 54370 | {'groups': 2892, 'retries': 190, 'range_errors': 535, 'response_errors': 2, 'cycles': 54370} |
| result | PASS | 29189 | {'jobs': 14, 'max_n': 12288, 'fault_cases': 8, 'retry_overwrite': True, 'cycles': 29189} |
| controller | PASS | 37053 | {'jobs': 28, 'max_n': 12288, 'n_matrix': [1, 7, 8, 9, 28, 29, 127, 128, 129, 255, 256, 257, 12288, 1], 'fault_cases': 12, 'collision_cases': 12, 'seed': '0x5184', 'cycles': 37053} |
| integration | PASS | 12301 | {'channels': 260, 'real_n2_k129': True, 'real_n129_k129': True, 'real_n129_k1': True, 'stage4_result_stall_edges': 168, 'ddr_requests': 265, 'ddr_beats': 527, 'cycles': 12301} |

主套件共 **136036拍**，逐拍比较所有公开输出的PRE/NBA；Controller/Integration另有 **62992条真实RTL事件** 与周期模型逐条相等。参数MAX_N=1的Result、65535的Result、257的Controller另有 **149615拍**；不能把65535的独立Buffer测试称为完整65535通道Stage4计算测试。

独立手写常量TB验证边界修正、正负双舍入、MIN与最终127、全零、33恢复、首错32后21升级锁定、Abort与GroupDone竞争。四项非法参数必须展开失败；三种runner探针证明$stop非零、缺PASS和FAIL+退出0都被拒绝。六个真实故意错误RTL（tie-even、对称上限、提前范围检查、double rounding、提前publish、尾数据污染）均由测试拒绝，日志中的FAIL为明确预期反向实验。

状态覆盖包括错Job/重复/跳号/逆序、Gap/连续Result、Group反压、retry覆盖、部分Job失败、Reset/Abort/上游错与word/commit/event/publish四相位竞争、首错与锁定、连续大Job再N1、旧RAM隔离。真实Stage4+5共260通道、265次DDR请求/527返回Beat，168个Result反压沿；原始A2值逐个与独立Stage4数学检查点一致。

Stage6预验证从实际RESULT_READ读回记录重新恢复31个Job、1807个word，检查exp/mask/顺序/尾0并与两Golden比较；测试软件再按Group每28个元素重分512bit并往返还原。没有实现Stage6生产RTL。

## 实测性能（采样沿定义）

| 128通道Group | 普通 | 一次Retry |
|---|---:|---:|
| 引擎start到最终word写，含起止沿 | 131 | 262 |
| 最后A2接收到GroupDone，含起止沿 | 135 | 266 |
| Retry额外沿间隔 | 0 | 131 |

所有量化Mantissa在一次attempt内间隔1拍。最后A2→首次q_valid相差3沿；→首次完整Result word写相差11沿（短Group为min(8,L)+3）。最后word写→commit相差2沿，commit→GroupDone相差1沿；最后GroupDone→JobResultsReady再1沿。收集从首A2到末A2的时间单列在PERFORMANCE.json，包含等待Stage4的时间，不混算算术延迟。普通/Retry完整Group样本分别108/2组；公式对每个实际完成Group长度都核对。

## 综合与时序边界

Yosys memory_dff/collect检查三块RAM各1同步读/1同步写，阵列无reset，零latch/组合环/乘法器。最终xc7家族探索映射：**1621 LUT、561 FF、7 RAMB36E1、0 RAMB18E1、0 DSP、6 RAM32M**。只统计Stage5，不含Stage0–4缓存与算术；这是Yosys家族映射，不是Vivado器件资源签核。

最长拓扑计数50个技术单元，路径经过RAM primitive，不能当成真实寄存器关键路径延迟、50ns或Fmax。实际关键时序/布局布线仍Pending。tools/vivado_stage5.tcl要求显式实际part和period，可对10ns/6.667ns探索；系统还须提供IO约束及共同reset释放审查。

## 复现

```sh
python3 tools/check_stage5_delivery.py
make stage5-test
make stage5-synthesis-check
make stage5-audit
```

Linux amd64无工具时：python3 tools/bootstrap_stage4_hdl.py --with-yosys，按输出设置PATH；TMPDIR设为可写目录。原回归为make py-test、make rtl-test、make stage23-test、make stage4-test。工具版本/命令/退出码/种子/向量SHA/事件全部保留。交付快照先校验再重跑，因为测试会重写证据文件。

## 剩余风险

1. Vivado2023.2、实际part/时钟/IO约束、布线时序及上板未执行；不承诺100–150MHz。
2. clean_boundary必须由未来上层真实保证；Stage4自己的sticky错误和DDR旧响应也须依冻结语义清理/复位。Stage5不能证明外部事务域干净。
3. 子模块rst_n是共同异步断言、同步释放后的本地reset；未来顶层必须保持共同复位域。
4. 定向/随机实测和数学证明不是机器形式化穷举；外部独立验收留待下一轮。

自审后无已知未解决的本地功能缺陷。没有commit、push、merge或创建PR。
