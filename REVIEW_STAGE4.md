# Stage 4 完整审阅入口

基线HEAD b67698ac6d318518ae328ab3ae91496f5a55b039，上传实际工作树bytes保留。冻结V1.0不变，原14个生产/标准/数值保护文件未改。本地Stage4验证PASS，Vivado/器件/时序和外部正式签核Pending。

先看docs/stage4/DELIVERY_REPORT.md、A2_PROOF.md、INTERFACE_AND_TIMING.md、DESIGN_SELF_REVIEW.md。四个新生产模块都在rtl/；新数值/周期模型在仓库根stage4_*.py；tb/有独立模块自检、真实Stage234联合和手写审查。

```sh
python3 tools/check_stage4_delivery.py  # 先核验交付快照，再运行会重写日志的测试
make all-tests
make stage4-synthesis-check
python3 tools/map_stage4_xc7.py
python3 tools/audit_stage4.py
```

需要Python3标准库、Icarus/vvp；结构与映射另需Yosys/ABC。无HDL工具时可运行可选tools/bootstrap_stage4_hdl.py（Linux amd64本地工具，不需root）。缺工具必须记Pending，不能用Python结果替代HDL。

logs/final_stage4_regression.log、五份*_hdl.log、review_hdl.log、compute_rtl_events.jsonl、PERFORMANCE.json、VERIFICATION_RESULTS.json和综合报告都在docs/stage4/。日志中的mutation FAIL与非法参数编译失败均为预期反例，见各自PASS判据。

sim_build/stage4/保留五份实际vec、vvp及网表，脚本可重生；mutations/下是故意错误RTL，仅用于反向实验，绝不是生产代码。rtl_sources.f只列12个生产模块。DELIVERY_MANIFEST.json给出交付文件SHA，SOURCE_CHANGES.patch为相对上传工作树的源码差异。完整包可直接运行，无需先应用patch；保留原Git历史并自行合入即可。

本核只输出signed48/signed16单通道结果，不生成最终BFP18 AXIS张量，不实现Stage5/6/7。
