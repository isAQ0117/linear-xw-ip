# Stage 6 + Stage 7 正式交付说明

当前阶段：6/7；子任务：完整实现、真实验证、性能统计、综合结构与最终自审。**本地 M=1 功能验收 PASS**，依据 XW-DEV-STD-001 V1.0 / XW-CONTRACT-STD-001 V1.0，无冻结契约变更。Vivado器件时序及真实DDR平台签核保持Pending。

## 状态与证据

|项目|状态|证据|
|---|---|---|
|Implemented|PASS|4个新增生产RTL；正式顶层10 Parameter / 35 Port|
|Python Numeric|PASS|Stage6两独立打包实现；完整Job逐Block/最终Requant交叉核对冻结numeric与Fraction Golden|
|Python Cycle|PASS|真实旧模块寄存器/RAM模型 + 新Output/Scheduler/Status模型，无人为算术延迟|
|RTL Module Simulation|PASS|Output 17317拍、Status 2453拍、Scheduler 129867拍，逐沿PRE/NBA全字段比较|
|Full RTL Integration|PASS|44个正常完整Job；4种Burst；静态/动态；默认MAX_N与MAX_K分别真实端到端|
|Global faults/recovery|PASS|35项场景，真实故障与诊断注入明确区分；7902拍逐沿比对|
|Synthesis Structure|PASS (Yosys)|完整顶层零Latch/组合环；8块逻辑memory合计552020bits，6块大RAM均同步读/写|
|XC7资源探索|PASS (Yosys)|17172 LUT、9128 FF、28 DSP48、13 RAMB36、15 RAMB18、81 RAM32M|
|Vivado Timing|Pending|未安装Vivado2023.2，未提供具体Part/时钟/IO约束，未执行布局布线|
|实际DDR平台|Pending|真实Burst、合法Latency/Gap及旧响应清理保证未确认|
|Stage8|未实现/范围外|没有多Batch、Weight Reuse或跨Tile调度|

新周期向量回归共 **692651拍**。另有独立手写unity端到端TB（两Job，分别长stall和始终Status Ready），9个非法配置展开拒绝、9个RTL突变检出与House Style检查。全部PASS以真实命令、退出码及唯一PASS标志为依据；故意错误日志有明确EXPECTED_REJECTION/MUTANT_REJECTED标签。

## 工程基线及源码保护

两份ZIP CRC和Git fsck通过。当前HEAD为 `ab17a13b42ce4e17512e339c8d9b90088adc6002`，采用上传工作树原始字节，没有checkout历史版本。初始20项tracked修改均为CRLF/LF差异，已保存初始Diff。冻结标准Markdown原始SHA与其发布Manifest因CRLF不同，归一化LF后匹配；DOCX原始SHA直接匹配。本轮不规范化或改写这些文件。

**原16个生产RTL、numeric.py和5份冻结标准，共22份保护文件逐字节不变。** 另有历史接口/RAM/周期/测试代码完整复用。旧回归本轮实际重跑，初次因没有/tmp在43项软件通过后中止；后续设置可写TMPDIR，Stage1/23/4/5、Stage4独立数值/手写/突变、Stage5全流程通过。原脚本重写的历史证据另存 `baseline_retest_snapshot`；上传历史原字节已恢复保留，不能将历史记录混为本轮结果。

核心审核包括正式标准、Stage23/4/5时序、16份生产RTL、数值与寄存器模型、现有Harness/生成器/运行入口。生成TB经原生成器重建和真实编译；历史JSONL/CSV/Manifest完整解析，DDR镜像从例子重建逐字节一致，DOCX ZIP/XML完整读取。附件House Style与仓库副本逐字节核对，没有安装或修改用户Skill。

## 实现与生命周期

- `xw_axis_bfp18_output`：4-word FIFO按count+pending预留RAM响应，跨word保留4项，静态72bit分段插入，最多每拍消费8项；独立完整AXIS槽保持所有数据和元数据。Stage5读口、共享指数和量化结果未改变。
- `xw_job_status`：单槽终态，不自行判定正确性；Status Valid/Ready稳态保持且不能覆盖。
- `xw_linear_scheduler`：Job所有权、尺寸锁存、完整地址预检查、真实Stage5 Ready、Scale按Group复用、Weight全行装载、Result握手、Group Commit、整Job发布、Output、Status和受控清理。
- `linear_xw_ip`：全部生产模块显式端口例化；没有Harness层级引用、仿真技巧、增加物理端口或公开Parameter。

静态模式完整忽略物理N/K（含0/65535）；动态模式只用接受沿锁存的值。首版仅M=1/M_TILE=1/P_N=1/P_K=8。任意尺寸/地址错误在AXIS ready和DDR命令之前返回01/02/03。

Scale Group→Weight Row→计算→Result握手→Group Requant/Commit→下一Group，严格串行，不重叠DDR/Compute。Result Valid单独不能推进。Stage5真正job_results_ready后才启动Output；最终EOT真实握手产生done，实测status_valid在之后2沿注册，最早Status握手再下一沿。Busy保持到Status握手；之后经过独立释放链和Ready确认才重新接单。

## 错误、锁定和清理

首码不覆盖；同沿系统/流失同步优先数值，同类按冻结表顺序。后到真实Receiver故障可升级Fault Lock而保留根因。配置01/02/03在未传输边界恢复；30–33仅在完整X、DDR无在途/寄存word/新命令时恢复。Status交付后才对数据域受控局部reset，Status/Scheduler/Receiver不受此局部清理影响；RAM数据不遍历清零。

所有AXIS失同步、DDR异常和内部40锁定，不能局部reset假装清除了外部旧响应。未完成Range的数值诊断注入实际验证了失败Status后Receiver仍busy、Job Ready仍关闭。无归属IDLE DDR返回只锁定，不制造Status。默认无硬件Timeout，缺响应测试有限观察1000拍后标为环境不可完成并由平台清理/Reset，**没有冒充0x22硬件超时**。

输出开始后，已接收片段无法撤回；严重故障停止新读/装配，已经宣告且stall的Beat保持到握手或外部Reset。失败Status可交付，平台必须按Job ID丢弃片段并清流。已发布Status也不可更改；Status等待期间迟到的平台故障只锁定后续分配，独立用例验证其不覆盖已发布成功终态。

真实顶层故障包括AXIS四类、非法Scale/FP8、BFP指数越界、额外DDR返回、输出前/输出中/最终EOT同沿故障、首错及晚到锁定。DDR_COMMAND/BUFFER、ACC_RANGE、INTERNAL_FAULT的全局路由另用**明确TB诊断注入**，不将注入当作产生该根因的算术或物理DDR验证。原Receiver/Buffer/A2模块回归另保留；合法顶层输入的有限数值指数本就不能自然逼近signed16 ACC指数上界。

## 关键端到端验收

|场景|实际结果|
|---|---|
|A N=2,K=129|6输入Beat、7 DDR Beat、2通道×2 Block、1输出Beat、1成功Status；每个B1/B2/A2/输出Bit-Exact|
|B N=129,K=1|2次独立Scale Group、129 Weight Row、两个不同共享指数、6输出Beat及最终EOT/Status|
|C 动态连续Job|K=127/128/129/2048/2049/4096/12288，不同N/ID、源Gap/AXIS反压、DDR Gap/同沿首Beat、Status长stall|
|跨Group Retry|N129/K1，首组131071.75附近RNE先得131072，真实Retry后65536/exp1；尾组131071/exp0，6 Beat正确|
|默认MAX_N=12288,K=1|真实顶层336580拍向量；12288通道、96组、12384 DDR Beat、480输出Beat|
|静态模式|两次N2/K129完整Job，物理job_n=0、job_k=65535仍成功|
|Output边界|所有Group Length 1..128及129/255/256/257/12288、signed18极值、尾padding/TKEEP/TUSER、最终stall、连续Job/Reset|

四个Burst Profile为1/2/3/64。44个正常Job的所有实际DDR请求，另用独立Layout V3枚举逐条验证。全部实际JSONL事件与Cycle Model逐条相等，冻结事件词表保留；每条带cycle/event/job_id/row及相关通道、组、block或beat字段。PRE握手与NBA生产沿明确定义，未人为平移参考事件。

## 性能与资源

完整128通道Group的Stage6无stall输出为 **22 cycles**，达到约20–30拍目标；没有每Mantissa串行等待。测试A profile3实测Job周期345（含有意39拍Status状态），其中纯Compute request→Result接受106拍，Input153、Scale7、Weight18、Requant9、Output6、Scheduler额外7。N129/K1对应3829拍。全表见PERFORMANCE.md/JSON，阶段占用来自每拍真实RTL比对通过的调度状态，外部事件来自RTL日志。

Yosys完整顶层资源为家族探索。552020bits是generic memory合计，不含已降低为FF的小Scale Cache等；RAM32M等另列。LUT/FF/DSP/BRAM不是指定Part的Vivado签核。最长拓扑计数可能跨RAM仿真模型，不是ns/Fmax，也不是寄存器关键路径时序。

## 交付与复现

复核入口 `REVIEW_STAGE67.md`；设计/端口：INTERFACE_AND_RECOVERY.md、PORT_REFERENCE.md；数值/周期：stage6_golden.py、stage67_golden.py、stage6_model.py、stage7_model.py；刺激/DDR Mock/Scoreboard/Fault Injection：test_stage6.py、test_stage7.py；模块/全链路TB及独立常量TB位于tb。

`sh run_stage67_tb.sh`重跑新增验收；`make all-tests`含旧回归与新增验收；`make stage67-synthesis-check`单独执行generic/xc7综合。工具缺失明确报Pending/失败，不生成虚假PASS。`tools/vivado_stage67.tcl`为待实用入口，必须明确Part/周期/真实Burst并补齐IO/平台约束。

完整源码Diff相对上传工作树，见SOURCE_CHANGES.patch；实际vec/vvp/综合JSON在sim_build/stage67，全部原始命令/退出码/RTL与模型事件在logs，最终SHA256 Manifest随包提供。没有自动commit/push/merge/PR。

## 未完成与限制

1. Vivado2023.2、具体FPGA资源/放置布线/时序/上板未执行，明确Pending。
2. 实际DDR Burst/Latency/Gap/旧响应清理保证待平台确认；无ID/Last不能识别所有错归属或迟到响应组合。
3. MAX_N和MAX_K分别用完整RTL Job覆盖，没有运行二者同时最大的大笛卡尔积工作量；默认容量在综合中真实展开。模块/调度/全链路分层覆盖均明确，未用小测试冒称全矩阵。
4. 有限仿真和独立数学交叉检查不等于机器形式化穷举或外部正式签核。
5. 本轮不实现Stage8多Batch/跨Tile/Weight Reuse，不改变冻结九阶段路线。
