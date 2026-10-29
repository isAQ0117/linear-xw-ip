# 独立设计自审

审查方式：在功能实现和首轮HDL通过后，重新从冻结合同、接口边沿与容量推导检查设计；不是外部独立审查签核。最终另跑全部软件/真实HDL与结构检查，日志独立保存。

## 位宽与边界

- K/N 为16bit、非零，MAX约束展开检查；ceil算式扩成17bit。K=65535得到512 groups、8192 X读取words、1024 DDR weight words、32 scale beats，均不溢出16bit内部计数。
- TUSER group_id9bit支持0..511；最终group后游标回绕只发生在input_end已锁定后，不再接收。group_start为17bit，group_len8bit可表示128，group_offset8bit 0/28/56/84/112。
- 18×28=504，高8bit必须零；尾beat按实际18L检查，包括有效字节内的padding bits。所有signed18作为raw18bit传输，signed8指数作为raw8bit独立保存，未误用无符号数值算术。
- 地址在64bit完整计算，全区间独占边界允许2^29，实际请求Start/End只在验证后截29bit。尾地址2^29-8的真实请求已有定向HDL轨迹；乘法无16/29bit中间溢出。
- physical word_index与segment_offset相加先扩17bit，合法输入上界1023，不丢位。乱序/越界写被Buffer拒绝，不因物理段变换重置逻辑written。

## 状态与时钟边沿

- AXIS仅握手沿校验/更新游标；旧header不会在stall时更新。Parser消费一个元素/拍，跨beat partial pack保留；组128恰好16×8，因此指数不会跨组拼接。
- wr_valid&&!wr_ready时不推进pack或beat；payload全部保持。最后beat EOT不会直接设Loaded，最后144bit实际提交时才设Loaded/Parser done。
- Receiver请求沿可收首Beat，word_valid为寄存器，Buffer在下一沿写。最后beat沿t后range_done，t+1同时写最后RAM并进入COMMIT，t+2之后才更改offset；没有offset先变、旧word后写的NBA错位。
- INIT按逻辑Group/Row仅一次；分段REQ稳定等待ready，无第二Outstanding。Loaded只在完整对象最后写入后出现，load_done还等待实际Loaded。独立时序断言与实际HDL事件日志交叉检查。
- 无硬件timeout。缺返回用定向测试等待40拍仍busy、不出done/fault，然后由外部清理/Reset结束；TB另有运行超时，不将挂起当异常处理PASS。

## 存储推断自审发现与修复

首版RAM写入与异步reset控制在同一always中，Yosys前端把数组展开成寄存器，虽然RTL功能/周期一致仍不适合作为最终存储实现。已拆分为无复位RAM时序块和可复位控制块；X同步读数据/指数，W同步读512bit后选8byte，read_seen使未初始化读输出不可观察为有效。Yosys memory_dff成功合并读FF，三个目标memory均clocked、无latch、check0问题。接口保持一拍，修复后全量HDL重跑。

旧Stage1 ScaleCache容量仅ceil(MAX_K/2048)×512（默认6 words），保持原实现；本轮未声称其已在Vivado映射为BRAM。新X/W大容量数组已用真正同步RAM结构。

## 无Ready DDR与错误传播

- W写口每拍可写512bit，ScaleCache已有同宽写口；没有把512bit拆成8拍而丢连续返回。接收空间预先覆盖完整逻辑对象，段间不清缓存。
- 全局fatal组合屏蔽AXIS ready、请求、公开Loaded/rd_valid，广播abort作废X/W有效标记；旧ScaleCache由ownership和public-valid门控隔离。故障后新load/cfg不能解除sticky锁，接新job必须外部清理后reset。
- 同沿AXIS10和DDR21按冻结表选择10；首错锁存后abort产生的次生40不能覆盖。已发布测试result遇到后续故障也保持payload；idle无归属DDR只锁定，不制造Job结果。
- 无ID/Last物理接口不能识别旧数据恰好落入新range或每种错误归属；本地reset不能证明外部flush。该系统前提仍Pending，未提供自动恢复承诺。

## 契约与范围

冻结标准文件逐字节不变，35-port ABI/DDR六信号/AXIS V2/Layout V3/B3-B-FP32均未修改。所有新增内部端口均有接口表；Harness是test-only，真实实现Job地址预检查早于任何AXIS握手。实现了部分缓存控制，不是Stage7 Scheduler，不输出完整IP成功Status。

Scale和Weight模块只搬运raw bits，数值合法性由未来Stage4消费控制接B2 scale_valid/FP8检查并产生30/31；本轮不宣称已实现Stage4数值异常链路。所有未执行的Vivado、时序、上板和真实DDR平台测试保持Pending。

结论：在报告列明的软件/HDL/泛化结构检查范围内通过；交由用户后续外部审查。无已知未解决的Stage2/3功能缺陷；不将有限随机仿真等同于形式化证明。


独立审查R1补充：此前P0-01/P0-02及P1-03已修复，详见docs/stage23/REVIEW_RESOLUTION.md（从仓库根定位）。所有PASS仅为本地可复现测试结果；外部独立复审和正式签核仍Pending。
