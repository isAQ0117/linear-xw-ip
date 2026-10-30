# Stage 6.0 / 7.0 实现前微架构冻结

标准 XW-DEV-STD-001 / XW-CONTRACT-STD-001 V1.0，不修改 ABI/数值/协议。
基线 ab17a13b42ce4e17512e339c8d9b90088adc6002，采用上传工作树；哈希见 BASELINE_SHA256.json。

## Stage 6

Output start/ready 携带已检查 job_id32/N16，仅整Job发布后启动。读口完整复用 Stage5。
4×(data144,exp8) FIFO；count+pending<4才请求。pending为上一个采样沿接受的一次RAM请求；响应必须恰好下一沿采样，校验index/mask/padding/组内指数。
每沿从FIFO消费至多8项；28边界可保留同一word的高4项。装配位置只可能0/4/8/12/16/20/24，静态72bit分段接线，不逐元素等待。
独立512bit输出槽，valid&&!ready时所有字段保持；已装满下一个beat之前可继续预取；slot占用时装配暂停。
最后EOT真实握手沿后产生output_done脉冲。halt停止新读/装配，保留已经宣告的beat至握手或外部reset，禁止假造done。
Status是独立一槽finish_valid/ready，锁存ID/OK/code，不自行判定成功。槽占用时不会覆盖，握手后下一周期才重新ready。

## 生产Scheduler与连接

IDLE→DIMS→CFG→CHECK→START→X→SCALE_REQ→SCALE_WAIT→WEIGHT_REQ→WEIGHT_WAIT→COMPUTE_REQ→RESULT→GROUP→PUBLISH→OUTPUT_START→OUTPUT_WAIT→FINISH→STATUS→CLEAN→REARM→IDLE。
DIMS使用真实xw_job_dim_cfg返回；先01尺寸，后02 M/TILE，再地址03。CFG调用已有64bit完整布局预检查；此前AXIS ready和DDR请求均为0。
START必须等stage5 job_ready、compute ready、output ready，实际start同时启动结果生命周期、Parser、XBuffer。job_start用锁存实际N。
Scale只在Group开始读取一次；地址模块load_done而非range_done驱动对象完成；Weight最后RAM提交后再发compute request。
RESULT只有result_valid&&result_ready推进通道；最后通道必须等待group_done，再切下一Group。最后Group等待job_results_ready，才启动Output。
OUTPUT_WAIT只在output_done后FINISH提交成功。Status握手前一直busy，握手后先清理再接单。
全部子模块普通命名端口连接；无生产层级引用。

## 首错、优先级与恢复（先于FSM编码）

|类|码|恢复|
|配置任务|01/02/03|未启动传输，Status后受控本地清理|
|流失同步|10/11/12/13|Fault Lock|
|DDR|20/21/22/23|Fault Lock，默认无22硬件源|
|数值|30/31/32/33|完整X且DDR无busy/寄存word/新command时任务级；否则Lock|
|不变量|40|Fault Lock|

同沿系统类优先于数值类，类内按冻结表顺序（10→11→12→13→20→21→22→23→40，数值30→31→32→33）；配置错误只在独立预检查状态产生。首次记录后不覆盖；晚到RX系统故障仍可升级Lock。
故障选择仅看原始模块诊断；取消引出的次生40不参与首错/升级。Receiver始终使用系统reset并继续监测外部响应，不受本地清理影响。
故障停新调度，失败Job不再提交result，Stage5收到已锁存根因并cancel元数据。已有Status不可改写；晚到故障仅锁定后续Job。IDLE无归属故障只锁定，无Status。
Status被接受后：可恢复Job进入CLEAN，用寄存复位释放链对Parser/缓存/Addr/Core/Stage5/Output清理，RAM不清零；两级同步释放后确认Stage5/Core/Output ready再回IDLE。Status、Scheduler、Receiver不在局部reset域，首错不会在交付前消失。锁定Job不做自动局部reset，不接新Job。
外部reset统一异步断言/两级同步释放。局部清理只在Status握手之后且干净边界进行，不承诺清除外部DDR旧响应。
输出中严重错误：停止预取，已有TVALID beat保持至被接受/外部reset；可交付失败Status，已接受片段由平台按Job ID丢弃。不能保证完成正常tensor，必须外部清流并reset。输出stall本身绝不触发错误。

## 平台配置

顶层仍10个公开parameter。编译宏XW_SIM_DDR_BURST显式选择仿真profile（1/2/3/64）；生产宏XW_PLATFORM_DDR_BURST需真实平台审核。两者不能同时定义，未选择profile展开失败。没有默认假定Burst、无DDR硬件timeout。
真实控制器型号、burst依据、响应最大latency/gap、旧响应清理保证均Pending。工具泛化综合不等于Vivado 2023.2具体器件时序。

## 周期口径

每行刺激为沿前，所有握手用沿前值；RAM等NBA产生事件标记生产沿，消费者下一沿采样。模型组合使用全部OLD snapshot。Stage6/7新增FSM延迟在本文件固定，不改变Stage1–5内部时序。
