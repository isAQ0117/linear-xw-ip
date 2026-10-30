# Stage6/7 最终源码自审

这是实现后的内部独立再审，不冒充外部审查签核。冻结标准与22份保护文件原字节不变。

|风险|核对结果|
|---|---|
|ABI|实际ANSI头部提取、独立35端口方向/位宽表、10参数顺序逐项相同；无公开DDR第11参数|
|Job锁存|实际N/K由真实dim_cfg提供，静态物理0/65535忽略；之后所有子模块使用锁存值|
|预检查|地址Generator64bit全区间预检查，含对齐/端点/溢出/重叠；错误前无输入/DDR传输|
|Stage5 ready|START必须实际Ready，独立替身停14拍不提前发start|
|加载/计算|load_done晚于物理Range和最终RAM提交；真实旧模块周期回归和全链路bit/cycle检查；不重叠DDR/compute|
|Result握手|仅valid&&ready推进，独立TB停3拍；忽略Ready mutant被拒绝|
|Group Commit|最后Result之后必须观察group_done；跳过Group等待mutant被拒绝|
|8→28容量|count+pending<4请求；响应把pending转入FIFO，pop只减少占用，归纳得count+pending≤4|
|半word尾部|N33定向发现half-word最多4项，不能消费尾剩余5项；修复后全部1..128长度及完整RTL通过|
|输出slot|所有字段只在空闲/真实握手时可覆盖；长stall和严重故障不撤销已宣告Beat；overwrite mutant被拒绝|
|TUSER/TKEEP|全部512bit和128bit元数据与两独立打包实现相同；offset是Group元素偏移，不是RAM index|
|最终EOT|done只在真实握手沿后注册；提前done mutant、独立已stall100拍及早Ready测试通过|
|Status|单槽保持，不覆盖；Busy到真实Status接受，之后释放链/Ready确认；每Job唯一终态|
|首错与Lock|分开保存；同沿失同步优先数值，后到RX异常升级lock不改根因；overwrite-first mutant被拒绝|
|次生故障|cancel引起的本地40不替代根因；取消后只有独立Receiver仍监测外部事务域|
|局部reset|仅Status接受后的CLEAN，寄存释放链；Receiver/Status/Scheduler隔离；不清大RAM阵列|
|输出后故障|保留advertised Beat，停止预取，允许失败Status；不宣称能够撤回已握手片段|
|不完整DDR|Receiver未被局部reset取消；dirty诊断注入后仍busy并lock；缺响应不主动发22|
|全链路Retry|定向N129/K1首组真实Retry、尾组独立指数，所有输出和周期实际RTL比对通过|
|数值|冻结FP8/FP32/B1/B2/A2/Requant模块完全未改；44正常Job所有检查点两Golden交叉一致|
|RAM/综合|8 generic memories，6大RAM同步1读1写，无Latch/组合环；tiny FIFOs可异步读；xc7探索非Vivado时序|
|RTL独立性|生产无TB层级引用；所有force仅在故障TB中；手写常量TB不读取Cycle Model期望|
|执行可靠性|vvp -N配合stop非零退出；runner还拒绝FAIL及缺失/重复PASS；9个mutant全部被检出|
|证据统计|阶段结果原先文件名互相覆盖已修正，并重跑全部新增矩阵；各阶段JSON独立保存|
|资源统计|曾误递归vendor仿真模型，已改为flatten顶层primitive计数；最终FF9128等来自原实际映射网表，未重解释为时序|
|历史保护|原回归改写的旧证据另存本轮snapshot，上传历史原始字节保留；不将历史PASS当本次执行|

没有已知未解决的本地M=1功能缺陷。Pending项及分层覆盖边界以DELIVERY_REPORT.md为准。未执行的Vivado/上板/真实DDR集成不标PASS。
