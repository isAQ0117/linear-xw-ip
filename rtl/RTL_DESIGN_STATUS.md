# Linear xW RTL 当前实现边界

冻结路线/契约 V1.0，M=1、P_N=1、P_K=8；无顶层35端口改动。

| 模块 | 状态 | 实测证据 |
|---|---|---|
| xw_job_dim_cfg | 原Stage1修订，保持原字节 | 原TB真实Icarus通过 |
| xw_ddr_range_rx | 原Stage1修订，保持原字节 | 原TB + 新PRE/NBA周期轨迹通过 |
| xw_scale_group_cache | 原Stage1修订，保持原字节 | 原TB + 新PRE/NBA周期轨迹通过 |
| xw_fp32_scale_b2 | 原Stage1修订，保持原字节 | 512独立Fraction向量真实HDL通过 |
| xw_axis_bfp18_input | 新Stage2实现 | 独立data Golden + 周期模型 + 真实HDL通过 |
| xw_activation_buffer | 新Stage2实现 | 同步144bit RAM，独立读写数据和逐拍检查通过 |
| xw_ddr_addr_gen | 新Stage3实现 | Layout V3预检查/逻辑对象/物理分段逐拍通过 |
| xw_weight_row_buffer | 原Stage3实现，保持原字节 | 512bit写/8-byte同步读，raw bits及mask逐拍通过 |
| xw_b1_dot128 | Stage4新实现 | 8lane乘法/三级树/48bit累加，真实HDL与周期通过 |
| xw_b2_fp32_pipe | Stage4新实现 | 原精确B2两级弹性包装，真实HDL通过 |
| xw_a2_accum48 | Stage4新实现 | signed128快路径/64bit分段特路径，每Block RNE通过 |
| xw_b3b_compute_ctrl | Stage4新实现 | 单通道/FIFO预留/结果反压/联合缓存计算通过 |

`tb/support/xw_stage23_harness.v` 为缓存联合测试支架，不是完整Scheduler或TOP；包含实际地址预检查门控和公共两级复位释放。
`rtl_sources.f` 仅列生产子模块，不包含Harness。

执行 `make rtl-test` 与 `make stage23-test` 可复现；详细日志/哈希/限制见
`docs/stage23/DELIVERY_REPORT.md`。
Yosys确认新大容量Buffer的同步RAM推断，Vivado 2023.2及FPGA实现仍Pending。
Stage4 B1/B2 Pipe/A2/局部Controller已实现并通过本地数值、HDL、周期和结构验证，见docs/stage4/DELIVERY_REPORT.md；Stage5 Requant/Buffer已实现并与真实Stage4连接；Stage6输出/Job状态、Stage7完整集成、Stage8多Batch仍未实现。


独立审查R1补充：此前P0-01/P0-02及P1-03已修复，详见docs/stage23/REVIEW_RESOLUTION.md（从仓库根定位）。所有PASS仅为本地可复现测试结果；外部独立复审和正式签核仍Pending。

## Stage5结果缓存

| 模块 | 状态 | 实测证据 |
|---|---|---|
| xw_output_group_buffer | 128×64同步RAM，接收时Hmax | 模块PRE/NBA、全字段边界通过 |
| xw_bfp18_requant | 单条精确RNE、最多一次原值retry | 两Golden bit-exact，模块HDL通过 |
| xw_result_buffer | 参数化144bit完整Job RAM、同步指数RAM | 尾mask/重试覆盖/同步读/参数65535通过 |
| xw_stage5_ctrl | 局部收集/提交/完成/首错及恢复 | 整Job/故障竞争/真实Stage4+5通过 |

完整证据见docs/stage5/DELIVERY_REPORT.md。xc7家族探索映射不等于Vivado实际器件时序通过；Stage6/7未提前实现。

Stage6/7：新增xw_axis_bfp18_output、xw_job_status、xw_linear_scheduler及正式linear_xw_ip。完整M1全链路/反压/错误/局部恢复真实Icarus验证通过，接口/证据见docs/stage67；原16个生产RTL字节不变。Vivado目标时序、实际DDR平台仍Pending，Stage8不在本轮范围。
