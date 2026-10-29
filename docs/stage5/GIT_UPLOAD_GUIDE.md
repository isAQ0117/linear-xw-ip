# Stage 5 GitHub Desktop 更新包

## 用途
这是 Stage 5 **精简源代码更新包**，不是原始 337 文件的 Stage 5 审查交付镜像。

## 复制操作
1. GitHub Desktop 中打开 `linear-xw-ip` 仓库，Fetch/Pull 远端 `main`；确认没有未提交的修改。
2. 解压 ZIP。直接复制**解压文件夹内部**所有文件/目录到已有仓库根目录，不要新建一层 `linear-xw-ip/`。
3. 允许覆盖 5 个改动的旧文件及 `.gitignore`。不要删除旧文件，不要覆盖 `.git/`。
4. 在 Changes 页面检查：新增 Stage 5 的 RTL/软件/TB/工具/文档、更新 `rtl_sources.f` 等；Stage 0–4 的 12 个生产 RTL 必须没有改动。
5. 可执行环境中先跑 Python/HDL 验证，确认后 Commit，再 Push origin。

建议提交：`feat(stage5): add requantization, result buffers and verification`

## 文件选择
- 保留 4 个 Stage 5 生产 RTL、Stage 5 Golden/周期模型/集成模型、Python 测试。
- 保留 6 个 Stage 5 TB + 1 个 Stage4/5 Harness、11 个工具脚本、`run_stage5_tb.sh`。
- 保留 5 个更新的项目配置/状态文件及接口、数值证明、正式验证与综合结构报告。
- 排除 `sim_build/stage5/` 内可重生的向量/网表/中间输出、`docs/stage5/logs/` 的原始日志、
  约 3MB 的 `NUMERIC_DECISIONS.jsonl.gz`、重复补丁、完整发布 Manifest 和 DOCX 文本缓存。
  已在 `.gitignore` 为相应路径添加忽略规则。
- 原完整 Stage 5 ZIP 应另外保留，尤其当以后需要核对原始日志和精确交付 Manifest 时。

## 重要的验证限制
- `tools/check_stage5_delivery.py` + `docs/stage5/DELIVERY_MANIFEST.json` 校验的是
  **原始完整的 Stage 5 交付包**。精简 Git 仓库故意省略生成文件，不应对精简库执行该完整校验。
  若要检查交付完整性，须使用原始 Stage 5 ZIP。
- `tools/package_stage5.py` 依赖其原始审查环境中的 `upload/02-linear-xw-ip-stage01234.zip`，
  不保证在普通 Git Clone 中能直接运行；不属于正常回归测试入口。
- Python 测试和 HDL 回归仍应按工具实际运行结果来判断。
  `make stage5-test` 依赖 `iverilog`/`vvp`，综合结构检查依赖 Yosys。
- 原始交付报告记录本地测试通过，但 Vivado 时序和外部正式签核 Pending。
  本精简操作不表示额外通过真实 HDL/板级验证。
- 重新运行工具可能更新已跟踪的 JSON 验证报告，请先审查 Diff 再提交。

## 完整性
原 Stage 0–4 上传 ZIP 包含 175 个工程文件；
Stage 5 ZIP 337 个工程文件（162 新增、5 修改、0 删除），
其原始交付 Manifest 336 项 SHA-256 校验全部通过；
与上版基线 175 个源文件哈希全部一致，除 5 个说明/配置文件修改。
此包额外提供一份独立的 Git 导入 Manifest（针对精简文件，而不是原完整交付）。
