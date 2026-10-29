# 最终独立自审

方法：功能实现后重新从冻结数值函数、数学定义、真实端口和上升沿推导，不以“软件PASS”推定RTL；独立Fraction Golden、手写RTL反例与故意错误RTL mutation交叉检查。未使用外部独立审查者，不代表正式签核。

| 审查点 | 结论与具体证据 |
|---|---|
| 数值独立性 | Level1A上传numeric字节不变；1B不导入生产解码/accumulate，Fraction+区间搜索；Level2使用独立整数硬件算法。每Block RAW/Term/pair三方比较；final result不是唯一检查点。 |
| B1有符号扩展 | signed18×signed19→37，逐层显式复制符号位到38/39/40，40→48复制8bit；全18bit边界/全合法FP8及mask尾部真实HDL通过。输入integer精确，不产生树顺序舍入。 |
| B2精度 | 原组合模块数学赋值原样；正sig的signed25保护未丢，72bit项不缩为56/BF16；最小subnormal/最大finite、非法零/负/Inf/NaN均实测。 |
| A2符号/范围 | 旧48/Term72先各自符号扩展到128，指数17bit比较及差值；特路径幅度72bit能容纳-2^71的绝对值；全字段546段实测，末carry/borrow非零报40。 |
| A2 RNE | 负数按幅度RNE再恢复符号；负2幂与非2幂分别处理signed48非对称；retry从原窗口再舍入。四个远处破tie向量及负boundary/sticky两个真实RTL mutant均失败，证明确有判别力。 |
| 零/抵消 | 零Term保留旧完整pair；旧state零不参与旧指数对齐；精确抵消保留target指数而不强改(0,0)。零Term2cycle与普通8/10cycle由实际FSM模型跟踪。 |
| 异常首次优先级 | 系统错误先于数值错误，数值同类30→31→32；首码sticky，后续真实fatal只升级lock；内部abort产生次生40不改根因。实际DDR21与NaN31同沿、Scale30和mask40同沿、后到fatal均实测。 |
| 无效结果 | Error分支优先于首次result发布；非法Scale不会以零Term绕过检查。手写TB在A2 COMMIT前注入21，A2_UPDATE/result均禁止。已发布正确结果按valid/ready契约在晚到fault时保持，reset/abort可撤销。 |
| FIFO容量 | 253bit完整条目包含两组data/mask、exp、slice、block、last。计数3bit表示4，指针2bit回绕，pending一拍保留请求归属。实际FIFO_LEVEL所有compute周期比较，max count/reserved均4；去掉pending的RTL mutant被TB拒绝。 |
| 时钟边沿 | 同步RAM t沿后出现response，Controller t+1沿入FIFO，B1随后采样FIFO旧head；组合模型所有子模块使用旧snapshot。PRE和NBA比较、21299条实际事件（显式row/group/job/channel/block）全一致。 |
| Reset/Abort | 生产模块接本地共同异步断言/同步释放复位；联合层复用原storage唯一release。valid与pending清空，大RAM不清数据。真实缓存响应在途reset/abort后无旧结果复活。 |
| 时序结构 | 无128lane乘法、无610bit移位/加法器。B1树寄存，B2输入/输出寄存；A2常规阶段分开，特路径65bit逐段。探测到归一化/提取组合链后缩窄移位量、预计算offset、分字节single-bit检测，周期保持。 |
| 性能 | B1每拍接受；全Block20，B2两槽2，A2常规8。实际Block32/40，启动33/41；每个Block保留A2顺序依赖，不为省周期延迟RNE。主要吞吐限制为单Block在途与A2提交后控制观察沿。 |
| 综合与限制 | 通用check零问题、无latch/环；映射47单元最长拓扑路径无ns含义。14DSP/6928LUT/2459FF/43RAM32M仅xc7家族探索。Vivado/实际part/100–150MHz/上板仍Pending。 |
| 历史与范围 | 原14个保护文件SHA全部一致；Stage4局部结果不冒充Stage5/6/7；原缓存重跑678659拍日志单独留存。无自动push/merge/PR。 |

自审中修复的实现/验证问题：初版控制错误组合屏蔽可能通过masked-valid形成反馈，已将producer abort与precommit错误拆开，最终Yosys无环；上游DDR失效不能被Loaded下降产生的40抢占，已改系统根因优先；已发布结果和发布前错误分开测试；覆盖统计的循环变量被后续短序列复用问题已修正，最终6894案例/13585更新。所有修订后的生产RTL均重新通过实际HDL、对应周期模型和最终结构/家族映射签名核对。

结论：在列明范围内没有已知未解决功能缺陷。目标器件时序、外部事务恢复、未来Scheduler对缓存所有权的保证仍需后续实际集成验证。
