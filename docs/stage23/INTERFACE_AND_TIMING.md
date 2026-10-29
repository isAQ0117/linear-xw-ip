# Stage 2+3 实现前接口与时序设计

当前阶段 2+3；子任务：接口/FSM/RAM 设计。冻结依据 V1.0 不变。下面均为内部接口，不是 35-port TOP；测试 Harness 不是 Stage 7 Scheduler。

## 公共边沿、复位与错误

所有握手采样上升沿 t 的沿前值；NBA 后为 t 的输出。内部 rst_n 须由系统异步断言、同步释放；Harness 唯一两级同步器驱动全部子模块。RAM 数据不复位，有效位/所有权清零。各模块首错锁存，fatal 仅 reset 清除；外部 DDR/AXIS 必须先清理。故障广播 abort 立即组合屏蔽 ready/rd_valid/loaded 和新请求，沿上清空所有有效标记，禁止读出旧缓存。因无 DDR Ready，Receiver 自身继续接收在途 Beat 或锁定，不能停钟。

## 接口表

| Producer → Consumer | 字段 | 采样与语义 |
|---|---|---|
| Harness → Parser | job_begin, job_id32, job_k16 | 仅预检查成功后单拍；M=1，内部锁存 |
| Parser → Activation | wr_valid/ready, data144, mask8, exp8, word_index16, last | 顺序 word 0..ceil(K/8)-1；stall 时全 payload 保持 |
| Harness → Activation | load_begin, load_k16 | 先于首 wr；K 容量检查 |
| B1 测试读 → Activation | rd_req, rd_word_index16 | 只在 loaded；word 对应 k=8*index，不能跨 group；同步一拍返回 data144/exp8/mask8 |
| Harness → Address Gen | cfg_begin,n16,k16,weight_base29,scale_base29 | 先完整布局预检查，cfg_done 单拍，cfg_error 为任务级 01/03 |
| 测试控制 → Address Gen | load_valid/ready, kind, index16 | kind0 group index / kind1 channel；一次完整逻辑对象，不能并行 |
| Address Gen → Cache/Weight | load_begin, total_words16, k_blocks16/k16 | 每个逻辑对象恰好一次，不随 segment 重发 |
| Address Gen → Receiver | cmd_valid/ready,start29,end29,beats16,kind | 完整保持到握手；single outstanding；包含式 end；物理 burst 参数必须显式提供 |
| Receiver → Buffer | word_valid,data512,index16,kind | 无 ready；index 为 segment 内索引，经 segment_offset 相加成为逻辑连续 index |
| Buffer → Address Gen | loaded,error,code | final Beat 真正写 RAM 后 loaded；Address Gen 下一沿才给 load_done |
| B1 测试读 → Weight | rd_req,rd_word_index16 | 8 FP8 bytes /64bit，mask8；同步一拍，最后字节不足时无效 lane 输出0 |
| B1 测试读 → Scale | rd_req,rd_scale_index16 | 复用既有 Cache 同步一拍，原始 FP32 bits，不在此阶段算 B2 |

读接口为 request pulse / registered valid，无输出 ready；未来 B1 必须只在可以消费时发 rd_req，可连续读每拍一个 word。读写并发、未 loaded 读、越界索引均为 40；X Buffer 本地乱序/越界写为40，DDR Weight/Scale Buffer写入错误为23。新 load 合法地失效旧内容，不解除 sticky 错误。RAM 同地址读写不允许，不依赖 vendor 的 read-during-write 行为。

## Stage 2 FSM 与 28→8

Parser `IDLE → ACTIVE → IDLE`，fatal 进入锁定。ACTIVE 内有 beat_shift512、remaining6、pack144、pack_lanes3、word output register。只在 beat 为空且 output 无 pending 时 ready。每拍消费一个 mantissa，写入 pack 的下一个 lane；第8元素或最终Tensor元素形成 144bit output，空 lane 为0，mask 为低 L 位1。partial pack 跨 AXIS beat 保留（28 mod8=4），group128恰好16 words，组界不会串 exponent。串行 unpack 为首版降低桶形搬移/多 RAM 写口复杂度，AXIS 有正常反压，不承诺每拍一个 beat。

header/sequence/payload/terminator 在接受沿校验，优先级 10→11→12→13；group_len/row/group/offset/组内 exponent 属 sequence。mantissa 高 padding 必须全零，keep 按 ceil(18L/8)，所有字段只在握手沿影响游标。accept final beat 只禁止更多输入，不能发布 loaded。最后 output handshake 沿 Buffer 写入并设 loaded，Parser 同沿发 done；Harness 观察下一沿，不能用 EOT 提前完成。

Activation RAM 为 ceil(MAX_K/8)×144；Exponent RAM 为 ceil(MAX_K/128)×8，只有 group 的第0word写 exponent。mask 从 K 和索引算，只有最后word可不足8。wr_last/mask/index 必须精确匹配期待值。每拍一个144bit写和一个同步读（互斥），无全 RAM reset。

## Stage 3 FSM 与分段

Address Gen `UNCONFIGURED/IDLE → INIT → REQUEST → RECEIVE → COMMIT → (REQUEST 或 WAIT_LOADED) → IDLE`。cfg_begin 在 IDLE 完整检查对齐、N/K、整个 W/S 独占末边界及重叠；算式用64bit（最大 N*RW*8），边界可等于2^29。cfg_error 不 fault-lock，允许后续合法 cfg；传输中的 cfg/load 冲突为40。load index 检查先于 INIT。

INIT 一拍仅初始化目标逻辑 Group/Row。REQUEST 稳定输出 base+8*offset 与 min(remaining,DDR_MAX_BURST_BEATS)。接受后 RECEIVE；同沿第一beat由 Receiver 收到，下一沿 word 才写 Buffer。最后物理 Beat 在 t 后变 word_valid/range_done；t+1 的 RECEIVE 观察 range_done 且 Buffer 提交同一 final word（offset 仍为旧值）；转 COMMIT。t+2 才增加 offset 或 WAIT_LOADED，避免 NBA 期间把最后 word 指向下一段。WAIT_LOADED 检查 buffer loaded 后脉冲 load_done。段之间不清 RAM/计数，完整逻辑 index=segment_offset+word_index。

Weight RAM 为 ceil(MAX_K/64)×512，能每拍无条件写一个512bit返回，读一拍选择8-byte slice。不采用8次写入的窄口方案，避免DDR连续返回丢数据。FP8 raw bytes 保留，非法FP8由未来Stage4消费控制检查；Scale raw bits同理，未来B2 scale_valid控制30。Stage2/3不把raw搬运误称数值合法性验证。

## Harness 预检查门控与边界

仅测试用控制：先 Job M/TILE/N/K检查，再 cfg_begin 给 Address Gen；cfg_done && !cfg_error 后才同时给 Parser/Activation job/load_begin。此之前 s_axis_tready 始终0，DDR cmd_valid 为0。非法地址实际拒绝，发测试 result 01/02/03，允许下一合法 job；AXIS/DDR/cache fatal 全局sticky，abort invalidate X/Scale/Weight。Harness 在 X loaded 后允许测试端逐个选择 Scale Group/Weight Row，再显式结束测试；不存在计算/输出成功Status，result 只代表缓存测试完成，不是完整IP的Job成功。

## 参数与限制

MAX_K/MAX_N 1..65535；M=1,P_N=1,P_K=8，DDR_MAX_BURST_BEATS 必须显式设置1..65535，0默认触发展开失败，避免将模拟值当平台保证。测试使用1/2/3/64/192。配置不提供硬件timeout，缺响应永远等待由TB timeout界定。未实现真正linear_xw_ip顶层、计算和输出；不发布系统完整验收。

## RAM 结构自审修订（接口周期不变）

最终实现将 Activation 与 Weight 的 RAM 访问放入独立的无复位 `always @(posedge clk)`；读数据寄存器不复位，由 `read_seen` 屏蔽上电未知值。X 的数据与 exponent 同沿读出；Weight 先同步读512bit，lane 与 mask 在同沿寄存，随后组合选择64bit，因此对B1仍为一拍读，不增加第二拍。控制、loaded、fault、read_seen、lane/mask依旧异步断言复位。所有读写 enable 使用同一组合合法性判断，冲突/abort沿不提交RAM写。Python Buffer显式包含ram_read_data、ram_read_exp、read_seen、read_lane。

Yosys `memory_dff` 确认输出FF合并进存储器，`opt_clean; check -assert` 为0问题：X 144×1536 + Exp8×96，W512×192（MAX_K=12288），每个1同步写口、1同步读口，无reset阵列、无latch。初始控制/RAM混写版本前端展开为寄存器，已纠正；初始日志仅保留为自审发现，不能当最终综合结果。目标Vivado BRAM映射和时序仍待验证。

## 独立审查R1修订与阶段4消费契约

本节优先于上文历史微架构描述。Activation本地Parser→X写入乱序、mask/last/exp/padding错误属于内部不变量破坏，一律40；只有DDR Weight/Scale接收缓存写入故障使用23，不改冻结错误码定义。Parser在job_begin周期组合屏蔽AXIS ready，重复begin锁定40且不会宣告接收Beat。Addr Gen保留内部load_done_reg，公开load_done = load_done_reg && !blocked；range_error、buffer_error、abort、reset或本地fault均立即屏蔽公开完成，包括Receiver在同沿NBA后才报告的错误。

X/W读取是无输出反压的固定一拍请求/响应接口，**不是带response-ready/hold的解耦握手**。rd_req在沿t接受，沿t后数据/valid可见，由下游在t+1沿采样；rd_req降为0后下一沿rd_valid降为0，不等待消费者。连续请求允许每拍一个返回。消费者必须在发请求时预留响应容量，并保持到响应被接收：

- 可预测stall：先停止发rd_req，再排空已经发出的响应；不能只暂停B1而丢掉在途响应。
- 不可预测stall：阶段4需在X/W读出口和B1间设置有容量预留的response保持寄存器/FIFO；占用+在途达到容量时不得再发请求。X/W的data/exp/mask必须作为同一条目保持，不允许只保持valid。
- 本轮不提前实现Stage4适配器。不满足上述预留约束的B1连接不在本轮验收范围；将来增加保持级必须同步模型和TB，不能把本轮一拍契约改写成已有rd_ready。
