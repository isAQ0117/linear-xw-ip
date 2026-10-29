# Stage5 独立验收入口

先读 docs/stage5/DELIVERY_REPORT.md、REPOSITORY_AUDIT.md、INTERFACE_AND_TIMING.md、NUMERIC_PROOF.md、STAGE6_READ_INTERFACE.md 和 DESIGN_SELF_REVIEW.md。

生产RTL只有新增4个模块：xw_output_group_buffer、xw_bfp18_requant、xw_result_buffer、xw_stage5_ctrl。旧12个RTL、numeric及冻结标准逐字节保留。stage5_golden.py是独立数学参考；stage5_model.py是实际FSM/RAM周期模型；tb/support/xw_stage45_harness.v真实连接旧Stage234和新Stage5，仍是测试Harness，不是Stage7 Scheduler。

```sh
python3 tools/check_stage5_delivery.py   # 重跑之前核对交付快照
make stage5-test
make stage5-synthesis-check
make stage5-audit
```

依赖Python3标准库、Icarus/vvp、可选Yosys/ABC。无系统HDL工具的Linux amd64环境可执行 `python3 tools/bootstrap_stage4_hdl.py --with-yosys`，按输出设置PATH；将TMPDIR设置为可写目录后执行原Stage0–4回归。工具包SHA固定，不改系统安装。

sim_build/stage5中的vec是本轮实际执行向量；生成器可重建。最终Manifest包含源、差异、日志、事件、数值决策、性能及综合报告。日志中的mutant FAIL、非法参数编译失败及runner故障探针是明确预期反例；正常5组模块/联合HDL均为PASS。不得把这些预期失败当成生产失败，也不得把Yosys映射当成Vivado Timing PASS。

完整源码差异相对本次上传工作树，不相对HEAD的CRLF版本；工程包已经包含最终文件，不必先应用patch。Git历史保留在用户原仓库；本轮没有commit、push、merge或PR。
