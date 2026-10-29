# Stage2/3 完整复审包 R1

先看docs/stage23/REVIEW_RESOLUTION.md，再读DELIVERY_REPORT.md。外部复审/签核Pending；本地测试通过不代替独立审查。

包含完整基线工程、四新RTL（rtl/下）、Golden、周期模型、全部TB/联合Harness、Makefile/filelist、原始日志、结果JSON、Manifest和Source Diff。没有打包.git或开发工具二进制，不包含凭据。基线commit和所有原始文件SHA在BASELINE_FILES.json。

验证包完整性（无需Git/HDL工具）：

```sh
python3 tools/check_delivery_manifest.py
```

从本目录复现（Python3、Icarus12.0；结构检查另需Yosys0.33）：

```sh
make py-test
make rtl-test
make stage23-test
make synthesis-check
python3 tools/check_review_mutations.py
```

make stage23-test自动执行所有周期轨迹、参数反例及新增手写审查TB。sim_build/stage23的vec/vvp由脚本生成，向量SHA见VERIFICATION_RESULTS.json；不需要下载额外权重，不依赖本环境的绝对工具路径。原日志记录了此次环境路径，复现时脚本使用解压目录。

日志与结果：docs/stage23/logs/、VERIFICATION_RESULTS.json、SYNTHESIS_RESULTS.json。SOURCE_CHANGES.patch是相对于4f3fc68f1f59ab83ae2f657356eec35a41d56e22的全部源码/文档差异；在该干净基线上git apply --check验证。完整工程可不应用patch直接运行。

Vivado2023.2、器件映射、时序和上板未执行。真实DDR规格及旧响应清理保证仍Pending。读取接口无rd_ready，阶段4消费约束详见INTERFACE_AND_TIMING.md的R1章节。
