# Stage 4 — GitHub Desktop 导入说明

本文件专用于精简 Git 仓库，**不是**原始 Stage 4 完整交付包。

## 导入方法
1. 在 GitHub Desktop 中确认当前是 `linear-xw-ip`，先 Fetch/Pull。
2. 确认工作目录没有未提交修改；可先备份工作目录。
3. 解压此 Overlay，把解压目录**内部的全部文件**复制到仓库根目录。
4. 允许覆盖已有的 5 个工程文件及 `.gitignore`，**不要**删除仓库中其他文件或 `.git`。
5. 检查 Changes：Stage 4 新源码/测试/脚本应全部新增，老的 8 个 RTL 不应修改。
6. 运行可用的本地测试，审查变化后 Commit、Push。

## 精简策略
- Stage 4 新增生产 RTL、Python Golden/周期模型、Testbench、执行脚本和主要验收报告全部保留。
- `sim_build/stage4/` 中的向量、vvp、综合 JSON 网表、故意出错的临时 mutant RTL 可由脚本重生，不加入 Git。
- `docs/stage4/logs/`、大型逐案例 Measurements / PERFORMANCE JSON 不纳入本次提交；重跑验证时可在本地生成。
- 原 Stage 4 `SOURCE_CHANGES.patch` 是交付时的差异快照；Git 提交本身会记录真正的变更，因此不重复入库。
- 完整交付清单 `DELIVERY_MANIFEST.json` 与 `tools/check_stage4_delivery.py` 面向原始 **269 文件完整发布包**。
  精简 Git Clone 缺少上述生成物，直接运行原完整交付哈希检查会提示缺文件，
  **这不是 Git 上传失败**。如需精确校验完整交付包，请对保留的原始 Stage 4 ZIP 解压后再检查。
- `tools/audit_stage4.py` 的旧基线 SHA 对行尾敏感；如果跨 Windows / Linux 出现哈希差异，
  先审查行尾转换，不要为了让校验通过而随意覆盖已冻结源码。

## 本次导入与测试状态
原始 ZIP 逐文件比较：122 个旧工程文件、147 个新增文件、5 个原文件更新、0 个旧文件缺失；
8 个 Stage 0–3 生产 RTL 与旧 ZIP 逐字节一致。
原始 Stage 4 交付包的 268 个 Manifest 项与对应字节全部匹配。
原始交付报告记录本地 Icarus / Yosys 相关测试 PASS；本次整理仅做 ZIP 字节、
文件布局、SHA 和 Python 语法静态检查，**没有在此重新执行 HDL 测试**。
Vivado 实际器件的综合、布局布线与时序仍为 PENDING；外部独立签核 PENDING。
