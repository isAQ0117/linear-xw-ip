# Stage 4 内部接口与时序（实现前方案）

固定V1.0，M=1/P_N=1/P_K=8。此为局部计算核，不增加35-port顶层，不实现Stage5/6/7。rst_n为共同异步断言、同步释放后的本地复位；abort撤销管线并锁定40，受控reset解除。错误first-wins，同沿40等失同步错误先于数值30/31/32；数值同类按30→31→32。已发布的下游结果valid/payload保持至ready或reset/abort。

B1输入slice valid/ready，data144（8×signed18）、weight64（8×rawFP8）、mask8、slice_index4、last、block_id16、act_exp8；单Block在途，16个Slice可连续接受，slice0开始，last关闭输入直至RAW交付。乘法寄存→4对和→2对和→1和→48bit累加；last的RAW寄存后valid保持。ID/exp/last随valid逐级；masked NaN不检查。出错清valid、不提交RAW。

B2包装锁存raw48/act_exp8/scale32/id16，下一拍寄存既有组合模块的term72/exp12/scale_valid；输出valid及错误随payload保持，零Term不能掩盖非法Scale。无截断或BF16。

A2 clear在channel开始使(0,0)，一次只接受一个term72/exp12/id16。update_valid表示内部完整state48/exp16提交，持续一拍；state在下次提交前稳定。零Term保持旧pair，精确抵消保留min exponent。快路径diff≤48用signed128对齐/加法；特路径以64bit分段精确加/减，只保存最高非零chunk和前一chunk及其以下精确非零判定。详见A2_PROOF.md。每Block提交后才开始下一Block。

Controller请求携带job_id32/channel16/K16；缓存loaded必须全为1且维度合法，否则40。局部request不是全局Job。Scale提前每Block读取并锁存；同步X/W请求共用word_index16=(block*16+slice)。深度4响应FIFO完整保存X144/W64/exp8/Xmask8/Wmask8/slice4，pending寄存器保存请求slice归属。count+pending<4才发请求，不依赖消费者未来ready；响应必须与pending以及X/W valid同时匹配。每拍最多一请求/一入队/一出队。支持消费暂停输入（slice_enable）用于局部节流/验证。FIFO对停顿完全安全。

Controller状态IDLE→SETUP→RUN→WAIT_A2→RESULT，数值/内部错误进入ERROR/LOCK路径。SETUP单拍发scale_req，可与首X/W请求重叠；RUN连续发slice，FIFO送B1；B1 RAW与scale送B2，B2送A2；A2 update后下一Block重新SETUP。最后update的pair交付result_valid/ready，带job/channel；失败不产生成功结果。局部error_valid/code/fault_lock由外层统一收口并负责作废缓存、外部DDR干净边界与Status。本核无DDR请求，不擅自清除Stage23缓存。

所有周期报告采用采样沿整数编号；注册输出事件B1_VALID/B2_VALID/A2_UPDATE标记首次产生沿（NBA后），不同于下一级握手沿。DDR加载、计算request→result首次valid、result stall分别计数。最终实测附录与PERFORMANCE.json覆盖本方案的确切实现延迟。

## 最终实现附录

实际端口清单见PORT_REFERENCE.md，由最终RTL逐端口提取。上述响应FIFO为253×4：X144+W64+exp8+Xmask8+Wmask8+slice4+block16+last1。默认MAX_K12288，展开支持1..65535，非法参数在命名guard处展开失败。外层必须保证req_k、job/channel与已装载缓存所有权对应；旧缓存没有暴露维度/标签，核心无法凭三个Loaded反查所有权。

Controller选择错误源时：有效的上游系统错误优先；本地内部不变量40优先于数值30/31/32；Scale读取时即复用原B2合法性检查。已锁存error_code永不覆盖；后续真实upstream系统错误可以进一步置fault_lock，内部abort产生的次生40不改变首错类别。数值错误保持error_valid并停止请求，等外层在干净边界作废缓存/复位局部核；本核不擅自重新装载缓存。error_valid没有ready，是sticky诊断，不是Stage6 Status。

B1/B2的out_valid&&!out_ready完全保持；A2update_valid是提交脉冲。result第一次发布时pair/job/channel一起锁存；已发布结果在反压期间保持，晚到上游故障只锁定后续请求，不改已发布payload；abort/reset可取消该结果。故障若在首次发布同沿出现，错误分支优先，不发布结果。尚未持有result时任何错误都不会制造result_valid。

B1数据/树寄存器无reset，valid使未初始化数据不可消费。B2是两个弹性槽（锁存与乘积），正常输入接受到TERM产生跨1个沿间隔，即按包含起止沿计2 cycles。A2快路径接受→ALIGN→SUM→ABS→LEAD→ROUND→CHECK→COMMIT，8 cycles；若第一次RNE溢出，基于原window增加shift并重复ROUND/CHECK，多2 cycles；零Term用ZERO路径2 cycles。特殊路径SETUP准备高Term相对offset、符号和段数，每CHUNK算一段；SETUP中预计算offset=-gap，每段+64，提取移位量只用合法6/7bit子段，避免gap减法/取负串联在64bit加减之前。每段工作窗口/精确sticky与证明一致，latency=chunk_count+6（retry再+2）。完整字段最多546段，不是合法Stage4常规性能承诺。

无stall的完整Block实测边沿（以当前Block第一RAM_READ沿R=0）：RAM请求0..15；FIFO/B1接受2..17；B1_VALID=21；B2_ACCEPT=22；B2_VALID=23；A2_ACCEPT=24；常规A2_UPDATE=31；特殊10段A2_UPDATE=39。下一Block第一RAM_READ=33/41。最终result_valid比最后A2_UPDATE晚1沿。Channel从compute_accept沿到首次result_valid按包含起止沿计数，完整常规J个Block为33*J+1；这仅为本次无stall/无retry数据的实测对应式，不替代一般Cycle Model。

控制开销：请求接受后1沿发首读；同步RAM+响应FIFO相对首读额外2沿后B1接收；Block结束后1沿由Controller观察A2提交并切SETUP，下一沿发读；末Block同一观察沿发布结果。FIFO满载恢复按count+pending<4保守发请求，不使用本沿pop预测容量，因此从满载解堵可有1拍额外空隙。人为slice_enable stall和result_ready stall单独计入报告。

联合Harness完整复用原Stage23 Harness的Job预检查、Parser、Address Gen、Receiver、三个真实缓存和公共local_rst_n，以测试层级引用共享reset/fatal诊断；此层仅用于仿真，不作为生产顶层。生产Core没有层级引用，单独可综合。测试显式控制加载对象/通道顺序，没有实现Stage7全局Scheduler。
