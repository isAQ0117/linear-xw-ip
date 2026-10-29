# Linear xW IP 当前状态（Stage 4 计算核心）

本轮上传HEAD `b67698ac6d318518ae328ab3ae91496f5a55b039`；以实际工作树bytes为基线，未提交/Push/PR。
冻结规则：XW-DEV-STD-001 V1.0 / XW-CONTRACT-STD-001 V1.0，未修改冻结原文或顶层ABI。

| 阶段 | 实现 | 软件 | 真实HDL | 结论 |
|---|---|---|---|---|
| 0 | 技术规则已冻结 | — | — | 平台规格仍待登记 |
| 1 | 既有四模块修订已确认 | 35/35回归通过 | 四TB、2参数反例、RX/Cache逐拍通过 | PASS（模块范围） |
| 2 | Parser + Activation Buffer | 数据独立Golden/周期模型通过 | Icarus逐沿比较通过 | PASS（M=1） |
| 3 | Address Gen + Weight Buffer，复用RX/Cache | 地址/原始bits/周期模型通过 | Icarus模块和联合逐沿通过 | PASS（缓存范围） |
| 4 | B1/B2 Pipe/A2/局部Controller已实现 | 独立Fraction/寄存器模型通过 | Icarus逐Block/逐拍通过 | PASS（局部Core；外部复审Pending） |
| 5–8 | 未实现 | 历史原型保留 | 未执行 | NOT_STARTED |

全部事实和限制见 [stage23/DELIVERY_REPORT.md](stage23/DELIVERY_REPORT.md)，逐项结果见
[stage23/VERIFICATION_RESULTS.json](stage23/VERIFICATION_RESULTS.json)。
Stage1旧报告中的HDL Pending为起始状态，不能覆盖本轮实际Icarus执行证据。

Stage4局部计算Core已实现；仍无完整linear_xw_ip顶层、Requant、AXIS输出或Job终态链路。
Yosys结构检查不等于Vivado综合/布局布线/上板通过。DDR真实Burst/响应延迟/旧响应清理仍待平台确认。


独立审查R1补充：此前P0-01/P0-02及P1-03已修复，详见docs/stage23/REVIEW_RESOLUTION.md（从仓库根定位）。所有PASS仅为本地可复现测试结果；外部独立复审和正式签核仍Pending。

Stage4最新证据见[stage4/DELIVERY_REPORT.md](stage4/DELIVERY_REPORT.md)。旧Stage23报告的Stage4未实现为历史快照。未修改任何冻结标准或Stage0–3生产RTL。
