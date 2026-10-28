# Linear xW IP 当前状态

## 版本事实
- 冻结技术合同：`CONTRACT_FROZEN_V1.0`，参见 `docs/standards/` 中的 Freeze Record。
- 源代码快照：`linear_xw_fp32_cycle_rtl_v0_2_ffn_style.zip`。
- RTL：4 个 Verilog-2001 模块；不是完整 Linear IP。
- TB：3 个模块级测试平台；`xw_job_dim_cfg` 的 TB 仍待补。
- Python：`test_cycle.py` 2/2、`test_fp32.py` 10/10 本次重跑通过。
- RTL HDL 编译/仿真：PENDING；没有实际通过的证据。
- Stage 0：冻结文件已归档，平台参数/前置审计仍应按合同补齐。
- Stage 1：IN_PROGRESS；正式退出前需真实 HDL 编译和模块测试。
- Stage 2~8：NOT_STARTED（按九阶段标准的验收口径）。

## 本仓库与原始 ZIP 的区别
- Python/RTL/TB 源文件字节内容保持原样。
- 原 `demo_results/` 仅被迁移为 `docs/verification/history/fp32_v0_2/`，
  避免再次执行软件模型时改动 Git 中的历史结果。
- 冻结标准原样放入 `docs/standards/`，第三份重复上传的开发标准不再存第二份。
- 新增 `.gitignore`、`Makefile`、`GITCODE_SETUP.md` 和源文件 SHA-256 清单。
- `README.md` 仍是上游软件模型 V0.2 的原始说明，不代表整体 IP 的签核状态。
