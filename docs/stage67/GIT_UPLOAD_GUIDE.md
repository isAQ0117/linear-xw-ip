# Stage 6/7 GitHub Desktop 更新包使用说明

## 这是什么
本 ZIP 仅包含 Stage 6/7 必需的 RTL、Python Golden/周期模型、Testbench、
工具脚本、关键技术合同和精简验证证据，**不是**原完整审查 TAR。

基线：用户上传的 Stage 0–5 Git 仓库快照
`linear-xw-ip-stage012345.zip`，main HEAD
`ab17a13b42ce4e17512e339c8d9b90088adc6002`。

## Windows GitHub Desktop 导入
1. 在 Desktop 选择 `linear-xw-ip`、`main`，先 Fetch origin；如显示 Pull origin，先 Pull。
2. 确认 Changes 没有尚未提交的修改，并检查基线；如果 main 已有其他更新，先核对差异。
3. 解压本包，**将解压目录内部所有文件和文件夹**复制进当前本地 Git 仓库根目录。
   不要再套一层 `linear-xw-ip/`，不删除旧文件，不修改 `.git/`。
4. 允许覆盖六个文件：`Makefile`、`README.md`、`rtl_sources.f`、
   `docs/PROJECT_STATUS.md`、`rtl/RTL_DESIGN_STATUS.md`、`.gitignore`。
5. 打开 Changes：确认新 4 个 RTL、5 个 Testbench、模型、测试、工具、文档齐全；
   不应有旧的 Stage 0–5 RTL 或冻结规范被修改/删除。
6. 尽可能在具备 Icarus Verilog/Yosys 的 Linux 环境回归，再 Commit 和 Push。

建议 Commit Summary：
`feat(stage67): integrate AXIS output, job status and Linear scheduler`

## 源代码和完整交付包的区别
- 保留 4 个生产 RTL、5 个 TB、4 个 Python 模型、2 个 Python 测试及 12 个 tools 文件。
- 保留接口与错误恢复契约、端口说明、平台配置、关键验收及性能结果。
- 排除 `sim_build/` 近 1 GiB 仿真向量、综合网表和临时文件；
  排除 `docs/stage67/baseline_retest_snapshot/` 的历史回归快照、*.log、
  源码 Diff Patch、完整交付 Manifest、SHA256SUMS 和 DOCX 文本缓存。
- 原 TAR 应单独存档，用于未来原始日志/逐字节交付审计。
- `tools/verify_stage67_delivery.py` 依赖原完整交付 Manifest 与生成产物，
  **不能用于精简 Git 仓库的完整性检查**。
- 一些 `tools/audit_stage67_inputs.py`/`tools/package_stage67.py` 和基线审计
  会引用原 review 环境的上传 ZIP；使用时要与日常 Git 回归区分。

## 检查口径
- 用户上传的基线 ZIP：225 个工程文件，Stage 6/7 TAR：582 个工程文件。
- 新包原始交付增 357，原文件改 5，原文件删 0。
- 原 16 个生产 RTL/Stage 0 冻结规范保持原样；生产列表扩展至 20。
- 原 TAR 的 580 条交付 Manifest 项已逐字节哈希核验通过。
- 此次仅打包和静态检查，不把交付报告记载的本地仿真当作本次重跑。

原始交付阶段状态：Stage 6 `PASS_LOCAL_ACCEPTANCE`，
Stage 7 `PASS_LOCAL_M1_ACCEPTANCE`；Stage 8 未实现。
Vivado 目标器件时序、真实 DDR 平台配置、外部正式签核仍 Pending。
