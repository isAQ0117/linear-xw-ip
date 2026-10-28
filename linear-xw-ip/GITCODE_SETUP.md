# GitCode 仓库初始化与日常管理

## 初次入库
在 GitCode 上先创建 **空的私有仓库** `linear-xw-ip`。
本 ZIP 是初始工作目录，尚未包含 `.git`，也没有上传任何远程代码。

```bash
cd linear-xw-ip
make py-test
git init -b main
git add .
git status
git commit -m "chore: import FP32 V0.2 sources and frozen contract V1.0"
git remote add origin https://gitcode.com/<owner>/linear-xw-ip.git
git push -u origin main
```
将 `<owner>` 替换为实际账号/组织，远程 URL 以 GitCode 仓库页面显示的为准。

## 后续每次开发
```bash
git switch -c stage1/job-dim-tb
# 编辑 RTL / Python / Testbench
make py-test
make rtl-test  # 需已安装 iverilog 和 vvp
git add rtl/ tb/ cycle_model.py linear_stream_model/ test_cycle.py test_fp32.py
git commit -m "test(stage1): add job dimension HDL testbench"
git push -u origin stage1/job-dim-tb
```
在 GitCode 提交 PR，审查后合并 main。个人开发可简化 PR 规则，但建议保留 main 可验证。

## 管理原则
- 单一仓库同时记录软件模型、RTL、Testbench、契约和少量验证证据。
- 修改数值/接口合同应同步修改 Python、RTL、TB；如果合同本身需要改变，按冻结基线的变更流程审批，不直接覆盖 V1.0。
- `docs/standards/` 保存冻结标准原文；不要改写历史文件。
- `docs/verification/history/fp32_v0_2/` 保存上传时的软件示例输出；新运行 `demo_results/` 会被忽略。
- 生成的波形/工具缓存/大文件不要纳入 Git，必要时保存精简的验证报告和复现方法。
- 只有真实 HDL 编译、模块级 TB 和相关验证满足合同后，才可以标记 Stage 1 PASS。
