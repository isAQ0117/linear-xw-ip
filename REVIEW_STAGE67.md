# Stage 6/7 独立复核入口

标准：XW-DEV-STD-001 V1.0 / XW-CONTRACT-STD-001 V1.0。上传工作树基线 HEAD：ab17a13b42ce4e17512e339c8d9b90088adc6002。未提交、Push、Merge或创建PR。

先读 [交付状态与限制](docs/stage67/DELIVERY_REPORT.md)、[接口/错误/恢复冻结](docs/stage67/INTERFACE_AND_RECOVERY.md)、[最终自审](docs/stage67/DESIGN_SELF_REVIEW.md)。

源码差异见docs/stage67/SOURCE_CHANGES.patch；逐文件哈希见docs/stage67/DELIVERY_MANIFEST.json及SHA256SUMS。patch相对上传ZIP工作树，而非忽略CRLF差异的历史HEAD。

- 生产RTL：rtl/xw_axis_bfp18_output.v、xw_job_status.v、xw_linear_scheduler.v、linear_xw_ip.v。
- 数值：stage6_golden.py、stage67_golden.py；周期：stage6_model.py、stage7_model.py。
- 刺激/驱动/DDR Mock/Scoreboard/故障注入及跨Group Retry：test_stage6.py、test_stage7.py。
- 自检TB：tb/tb_xw_axis_bfp18_output_cycle.v、tb_xw_job_status_cycle.v、tb_xw_linear_scheduler_cycle.v、tb_linear_xw_ip_cycle.v；另tb_linear_xw_ip_known_answer.v独立常量。
- 编译/运行：tools/run_stage67.py、review_stage67.py、check_stage67_synthesis.py、report_stage67.py、audit_stage67.py、run_stage67_tb.sh及Makefile。
- 实际向量、vvp和综合网表：sim_build/stage67；事件、命令、退出码与原始日志：docs/stage67/logs；旧回归本轮重写的历史证据另存baseline_retest_snapshot，上传历史原字节已保留。

普通工具环境运行 `sh run_stage67_tb.sh`；完整含旧回归执行 `make all-tests`，资源检查单独执行 `make stage67-synthesis-check`。这些流程为串行，避免生成TB/日志相互覆盖。

Vivado入口tools/vivado_stage67.tcl必须明确PART、周期和审核后的DDR Burst；这份脚本尚未在Vivado运行。不得使用仿真Profile宣称平台部署已通过。
