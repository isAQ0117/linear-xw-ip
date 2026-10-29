# Linear xW IP 当前状态（Stage 2+3 联合开发）

基线 main `4f3fc68f1f59ab83ae2f657356eec35a41d56e22`；本轮仅工作目录修改，未提交/Push/PR。
冻结规则：XW-DEV-STD-001 V1.0 / XW-CONTRACT-STD-001 V1.0，未修改冻结原文或顶层ABI。

| 阶段 | 实现 | 软件 | 真实HDL | 结论 |
|---|---|---|---|---|
| 0 | 技术规则已冻结 | — | — | 平台规格仍待登记 |
| 1 | 既有四模块修订已确认 | 35/35回归通过 | 四TB、2参数反例、RX/Cache逐拍通过 | PASS（模块范围） |
| 2 | Parser + Activation Buffer | 数据独立Golden/周期模型通过 | Icarus逐沿比较通过 | PASS（M=1） |
| 3 | Address Gen + Weight Buffer，复用RX/Cache | 地址/原始bits/周期模型通过 | Icarus模块和联合逐沿通过 | PASS（缓存范围） |
| 4–8 | 未实现 | 历史数值原型保留 | 未执行 | NOT_STARTED |

全部事实和限制见 [stage23/DELIVERY_REPORT.md](stage23/DELIVERY_REPORT.md)，逐项结果见
[stage23/VERIFICATION_RESULTS.json](stage23/VERIFICATION_RESULTS.json)。
Stage1旧报告中的HDL Pending为起始状态，不能覆盖本轮实际Icarus执行证据。

仅实现测试Harness，尚无完整linear_xw_ip顶层、计算、Requant、AXIS输出或Job终态链路。
Yosys结构检查不等于Vivado综合/布局布线/上板通过。DDR真实Burst/响应延迟/旧响应清理仍待平台确认。


独立审查R1补充：此前P0-01/P0-02及P1-03已修复，详见docs/stage23/REVIEW_RESOLUTION.md（从仓库根定位）。所有PASS仅为本地可复现测试结果；外部独立复审和正式签核仍Pending。
