# 最终独立源码自审

方法：实现后重新从冻结numeric.py、精确数值定义、最终RTL边沿和实际RAM使能检查，另用独立Fraction Golden、手写常量TB和故意错误RTL交叉验证。这是内部重新审查，不冒充外部独立审查者或正式签核。

| 风险 | 审查结论/证据 |
|---|---|
| signed48最小负数 | 无符号48bit补码幅值表示2^47，前导位=47；H用signed18加法，不在signed16中溢出。模块含完整字段极值。 |
| 指数宽度 | H范围[-32768,32814]，候选/修正和差值均signed18，右移差界65567；截8bit只发生在最终CHECK通过后。 |
| 优化与最优指数 | H−17必失败；H−16至多产生131072，增加1后≤65536。严格推导和两Golden+有限位宽原型交叉比较。 |
| 负RNE/ties | 先幅度，guard/sticky/奇偶进位，最后恢复符号；右移48的MIN tie取偶0，>=49严格小于half。逐移位边界与RNE决策记录已核对。 |
| Double rounding | retry重读原64bit State RAM。[(262143,0),(5,-1)]正负反例实际RTL和手写常量TB通过；double_round mutant被拒绝。 |
| 对称幅度 | 19bit临时值覆盖±131072；engine只允许最终abs≤131071。Result Buffer另记录本次attempt出现18'h20000，允许投机写但禁止最终commit，retry清此标志。独立Buffer反例验证40。 |
| 零与padding | 全零exp0，零输入极端指数不影响Hmax。尾元素只扫描真实length；非零Group整体量化全零数学上不可能，小项下溢实际覆盖。 |
| 元素/归属 | Stage4真实端口直接连接，握手沿写一次，job/channel严格递增核验，非法项不写。完整组/尾组/连续Gap/168个真实Stage4反压沿均核对。 |
| 同步RAM | 64×128、144×ceil(MAX_N/8)、8×ceil(MAX_N/128)各1同步写口/1同步读口，数据阵列无reset循环；Yosys memory_dff/collect确认。 |
| Word组装 | 固定8 lane选择，避免动态144bit写选择的乘法节点；初始lane清pack，完整Word同沿全宽写，尾lane0，retry覆盖真实全部word。 |
| 原子提交 | 最后Mantissa写完成后2沿才写指数/提交前缀，再1沿才GROUP_REQUANT，再1沿才最后JobReady。投机数据不能读取；错Job/错序/部分失败不publish。 |
| Reset/Abort | RAM使能和公开有效信号组合屏蔽cancel；控制异步reset。最后word、commit、group事件、publish四相位各与reset/abort/upstream错误交叉共12组，均无虚假成功。 |
| 错误恢复 | 首码sticky，上游系统优先、本地40先于新数值错；已锁存30/31/32不被取消产生的次错覆盖，后到21仅升级lock。任务33需clean边界及retire；系统锁定只能reset。 |
| 旧数据泄漏 | 新Job取消读授权/提交前缀/read_seen；从MAX_N Job到N1实际重新读取，尾高lane为0；失败Job不开放任何读。 |
| 周期模型独立性 | 模型按寄存器/FSM/pending旧快照组合；数值期望来自Fraction/original两Golden；手写常量TB和6个mutant降低软件/RTL共同错误风险。 |
| 实际周期统计 | RTL $fdisplay给出接受/读/量化/word写/commit/group/JobReady/Result读；与模型逐条比较。收集含Stage4等待单列，不计入算术延迟。 |
| 综合与时序 | 无latch/组合环/乘法器；xc7映射只作资源探索。最长拓扑路径跨RAM primitive，不能直接视为实际寄存器关键时序或ns。Vivado/具体part/约束/100–150MHz仍Pending。 |
| 范围 | 没有改旧12个RTL、numeric、冻结标准或35-port ABI；没有Stage6 sender、全局Scheduler、多Batch、最终Job Status。 |

自审修正：固定8 lane组装取代前端常数乘法节点；增加Result Buffer attempt幅度拒绝提交标志；修正人工Gap源使valid在stall期间持续保持；补充真实RAM读记录和28-lane测试软件往返。上述更改后重新跑完整Stage5软件/HDL/手写审查/突变/参数/结构/映射；没有仅靠旧PASS签名交付。

没有已知未解决的本地功能缺陷。有限定向/随机仿真与数学界限证明不等于对全部signed48×signed16字段的机器形式化穷举。外部DDR/AXIS干净边界、共同reset释放及未来Scheduler对缓存归属的保证仍由系统集成负责。
