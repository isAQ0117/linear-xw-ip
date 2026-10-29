# 开发前仓库审计（2026-10-28）

当前阶段：2+3 联合任务，子任务：源码准入。依据 XW-DEV-STD-001 V1.0 / XW-CONTRACT-STD-001 V1.0。冻结标准原文不修改。

## 版本与读取范围

在线实际执行 `git ls-remote --symref ... HEAD` 并 clone。默认分支 main，HEAD `4f3fc68f1f59ab83ae2f657356eec35a41d56e22`。历史为 0024bc6 → 99f4902 → e775e8e → 4f3fc68。
附件 SHA256 `4ba9dbcfed7d1bb52d4f3c18ee82b439e4c8a410f04f7792cf0d70d7f4cadaaa`。ZIP **没有 .git / Git 历史**，与用户描述的差异据实记录。50 个文件的路径集合与在线 tracked files 相同，全部逐字节相同。因此工作目录使用在线 clone，没有以 ZIP 覆盖源码。

`BASELINE_FILES.json` 记录全部 50 个受控文件的完整目录、长度、SHA256。逐文件实读全部 RTL、TB（含 negative）、Python、shell、Makefile、filelist、Markdown、JSON Manifest/报告。示例 JSON 全量解析并重跑；JSONL 全部解析、输入/输出重解包；CSV 全部 10 行解析；B2 mem 全部 512 行由独立 Fraction 校验再现。不存在未检查的大文件。

二进制检查：DDR image 为 1024 bytes / 16×64B，与例子 N=5,K=129,M=2 经 Layout V3 重建的 bytes 完全一致；全部 weight、scale、padding 均被比较。DOCX 为有效 OOXML（19 parts，CRC 通过），document.xml 全文提取到 BASELINE_DOCX_EXTRACT.txt；技术依据为同名冻结 Markdown。Git 对象由 clone 获取并另外运行 fsck。

## 实际依赖与已知问题

- 四个 RTL 已包含 Stage 1 修订：Receiver 0x20/21 sticky、handoff hold；Cache 0x23/40、冲突保护；Job 参数展开保护；B2 signed72 保留。
- 原软件只依赖 Python 标准库。V0.2 cycle_model 是架构模型，其用户指定 latency 不是 RTL 周期；M>1 demo 不构成本轮 M=1 硬件支持。
- PROJECT_STATUS.md 的“三份 TB / dim TB 未补”已经过时，实际四份 TB。README/冻结记录中的平台和 HDL 状态是历史记录，本轮报告覆盖当前执行事实但不改历史冻结文件。
- SOURCE_IMPORT_MANIFEST 描述导入前版本，RTL/TB 改动导致旧哈希不匹配；CSV 为行尾变化（需规范化比较）；stage1_source_manifest 仍有 demo_results 的旧路径、自身哈希与 README 历史差异。均不能当当前签名清单。使用新基线 Manifest。
- 现有子模块 rst_n 是本地复位，直接异步释放并不实现系统同步释放。本轮 Harness 在公共边界加入两级释放同步，子模块使用同步释放后的同一复位；不得给各流水模块串接不同复位延迟。
- 未获得真实 DDR Burst/Latency/Gap/旧响应清理规格；模拟参数不是平台规格。无硬件 timeout；DDR 无 ID/Last 无法检测全部错归属数据。

## 起始验证状态

先运行现有 `sh run_stage1_software.sh`：35/35 PASS，B2 512 vectors reproducible。初始环境无 iverilog/vvp/vsim/verilator/vivado/yosys，HDL 仍 PENDING；后续若成功准备本地真实工具，以本轮验证报告记录实际结果。不得将软件 PASS 当 HDL PASS。

任务授权允许记录风险推进阶段 2、3；不实现 Stage 4–8，不改变九阶段路线或任何冻结外部 ABI。
