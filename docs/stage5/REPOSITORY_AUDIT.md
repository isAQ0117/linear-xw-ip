# Step 5.0 仓库审计与冲突处理

当前Stage5；冻结依据XW-DEV-STD-001 V1.0 / XW-CONTRACT-STD-001 V1.0；无标准偏离。

两份上传ZIP已实际解压、CRC检查；Git HEAD为a6010b91105164b139afcc7324e17e205b09ef63。初始文件树、大小、SHA256、Git工作区状态及ZIP哈希保存在UPLOADED_BASELINE.json。175个非Git数据文件全部纳入全文/格式/依赖审计，最终分类目录见AUDIT_RESULTS.json。关键生产RTL、数值/周期模型、接口契约、运行生成脚本和审查材料已对照；自动生成TB另经原生成器逐字节重现及真实HDL执行。大向量/JSONL/CSV完整解析，历史DDR镜像从原例子重建逐字节一致；DOCX内部ZIP/XML完整读取，全文另存BASELINE_DOCX_EXTRACT.txt。

附件Skill的SKILL.md、reference、模板、检查器及其单元测试已读取并与仓库tools/rtl_house_style副本逐字节核对。新RTL/TB依其ANSI、集中声明、中文功能注释、四空格和Verilog2001规则编写；没有安装/修改用户Skill。

初始20项Git修改经与上传ZIP及HEAD比较，均仅CRLF/LF差异。没有checkout旧版本，没有清洗这些原字节。旧12个生产RTL、numeric.py及5个标准文件，共18个保护文件最终SHA全部一致。

发现并记录的差异：

1. PROJECT_STATUS、Stage4报告的HEAD是先前快照，与本次实际HEAD不同；本轮使用上传工作树bytes。
2. 九阶段标准的末章和Freeze Record中的工程Pending是历史快照；技术冻结规则已生效，当前阶段进度由现存实现和本轮实测决定。
3. Stage4历史报告提到DELIVERY_MANIFEST.json、日志及性能文件，但上传包未包含其中若干文件。不能把其文字当本轮证据；已重跑原43项软件、Stage1/23/4真实HDL并保存新日志。旧报告原字节恢复保留，本轮基线日志独立放在stage5/logs/baseline_*。
4. 原cycle_model.py含可配置算术延迟，只用于历史架构模型；新stage5_model.py按RAM/FSM/流水寄存器逐拍实现。
5. 原requant_bfp18从Hmax−17开始，任务建议从Hmax−16开始；前者必溢出一次，独立证明后采用后者，不改numeric.py。
6. 原Stage4审计工具把RTL文件数固定为12；Stage5扩为16个，当前审计入口为tools/audit_stage5.py。旧工具/交付快照不是本轮签名。
7. 首次基线make all-tests因环境没有/tmp而在原mktemp处停止，软件43项已过；设置工作区TMPDIR后原HDL全套成功。两个尝试日志都保留，未修改旧运行脚本来掩盖环境问题。

Stage4接口核实：result_valid由result_pending产生，payload四字段同时锁存；无ready时保持，只有采样沿valid&&ready消费；晚到上游故障可保留已发布payload，因此Stage5还接收独立upstream_fault/code/lock并立即禁止接收/提交。GB的result_ready独立于valid；满组量化时反压，不消费同一条Result两次。

X/W/Scale缓存都是固定一拍无response-ready的同步读；本轮沿用此边沿定义。Stage5自己的Group RAM、Result Mantissa RAM和Exponent RAM采用独立无reset的同步访问块，由有效前缀/Job状态授权，读写阶段互斥。
