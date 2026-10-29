# 本轮执行入口

所有命令从仓库根执行；逐项compiler/vvp/yosys参数和退出码见logs。

```sh
python3 tools/bootstrap_stage4_hdl.py --with-yosys
PATH="$PWD/sim_build/toolchain/bin:$PATH" make all-tests
# 上条原脚本因缺/tmp停止；下条设置可写TMPDIR后原HDL全部通过。
PATH="$PWD/sim_build/toolchain/bin:$PATH" TMPDIR="$PWD/sim_build/toolchain/tmp" make rtl-test stage23-test stage4-test
PATH="$PWD/sim_build/toolchain/bin:$PATH" python3 tools/run_stage5_all.py
PATH="$PWD/sim_build/toolchain/bin:$PATH" python3 tools/check_stage5_synthesis.py --map
python3 tools/audit_stage5.py
git fsck --full
```

最终日志为final_stage5_regression.log及各子日志；早期修正前报告不覆盖最终VERIFICATION_RESULTS、REVIEW_RESULTS和综合SHA。
