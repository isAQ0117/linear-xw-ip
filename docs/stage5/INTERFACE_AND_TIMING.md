# Stage 5 接口与逐拍契约（Step 5.0，RTL 前冻结）

当前 Stage5 / IN_PROGRESS；遵循 XW-DEV-STD-001、XW-CONTRACT-STD-001 V1.0，无标准偏离。
基线 HEAD a6010b91105164b139afcc7324e17e205b09ef63；使用上传工作树字节，旧报告中的 HEAD 是历史快照。

## 模块边界

| 模块 | 输入/输出 | 所有权 |
|---|---|---|
| xw_output_group_buffer | begin_group + job/base/len；原 Stage4 六项 result_*；同步 rd_req/index → rd_valid/mant/exp；loaded/nonzero/hmax/error | 当前唯一 Group 的 128×64 RAM；接收沿同时更新 Hmax，禁止二次扫描 |
| xw_bfp18_requant | start/len/nonzero/hmax；同步 RAM 请求/响应；无反压 q_valid/index/mant/last；attempt_begin；done/exp/retried/error | 一条 RNE 通路；READ→DRAIN→CHECK，必要时 RESTART 从原 RAM 重读 |
| xw_result_buffer | job_begin/N；attempt_begin/group/len；q stream；commit/exp；publish；同步读端 | ceil(MAX_N/8)×144 Mantissa，ceil(MAX_N/128)×8 指数；按顺序 committed_count 授权 |
| xw_stage5_ctrl | job_start/job_ready/job_id/job_n；原 Stage4 result_*；upstream_fault/code/lock；clean_boundary；retire；abort；读取端 | 局部 COLLECT→WAIT→COMMIT→PUBLISH→NEXT/FINAL→COMPLETE；错误进入 FAILED |

MAX_N 默认12288，合法1..65535。N 已由上层确认，非法内部配置报40。job_start只允许job_ready=1；retire仅在COMPLETE/FAILED且clean_boundary=1并未锁定时允许；这不是Stage6 Status。ERROR=33只有clean_boundary=1才允许任务级回收；否则锁定。系统级40/上游lock只能受控reset恢复。旧Stage4数值错误仍需上层在干净边界复位它自己的sticky诊断。

rst_n为共同异步断言、同步释放后的本地复位，顶层未来提供公共释放同步。优先级：reset > 首个系统错误/上游故障 > 数值错误 > 正常提交。abort无上游根因时为40；伴随上游错误的取消保留其根因。首码不覆盖，后到系统故障只升级lock。错误/abort同时屏蔽写入、commit、group_done、job_results_ready及读valid。RAM无复位循环。

## Stage4 接收

result_valid/result_ready在上升沿同时为1才接收。payload为signed48/signed16/32bit job/16bit channel，与原 xw_b3b_compute_ctrl 同名直接接线。ready不依赖valid。只在COLLECT且Group未满时为1，量化和换组时反压。握手时校验job和严格连续channel；错误条目不写RAM。满组最后一写完成后loaded有效，下一沿启动量化。每个正常收集沿最多接受一个Result。

H范围[-32768,32814]；candidate范围[-32784,32798]，retry后最大32799。指数和差值使用signed18，最大右移差65567。abs48用无符号48bit补码幅值，可容纳2^47；非零合法左移最多16。右移仅1..47进入48bit移位器，>=48恒为0（-2^47/2^48为偶0 tie），零mant忽略指数。输出通路为19bit带符号临时结果，溢出标志判断abs>131071；仅18bit payload写入投机RAM，不对外有效。

## RAM、原子提交与周期

组内 i 地址0..127，{exp[15:0],mant[47:0]}。读请求沿r之后rd_valid/data有效，engine在r+1沿采样。一次只能收集或读取，不定义同址读写模式。

Result A_R(g,s)=16g+s，lane l放[18l+:18]；q每拍一项，第8项或尾项沿将assembled完整144bit写RAM，未用lane置0。retry重新从q_index0写，前一次不commit。指数仅最终commit沿写入。committed_count是顺序有效前缀，不需要清RAM；job_begin/cancel归零。只有所有Group已commit并收到publish才置job_results_ready。

若最后A2接受沿F，Group长L：F+1 start；F+2首次RAM读；F+3首次q寄存；F+4首次q被buffer消费（L<8时同时写首word，否则第8项时写首word）。最后q消费/最后word写在F+L+3；同沿engine CHECK确认最终指数。F+L+4 controller观察done；F+L+5 commit指数和有效前缀；F+L+6发布GROUP_REQUANT；最后组F+L+7发布job_results_ready。普通128组F→GROUP_REQUANT相差134沿，包含两端135cycles。retry增加L+3沿；实测会逐项核实。

GROUP_REQUANT表示最终数据/指数已真实写入，事件在注册group_done产生沿，非下级消费沿。事件job/group/len/exp随group_done注册，不能以递增后的游标代替。最后JobReady单独晚一沿，绝非Job Success Status。

## Stage6 读取合同

rd_req && rd_ready的沿接受，rd_word_index为全Job word序号0..ceil(N/8)-1。只在job_results_ready后ready允许；越界请求在已发布Job时是40。响应rd_valid/data144/exp8/mask8/index16在该沿后有效，下级在下一沿消费；可连续每沿请求。无response_ready：Stage6须在请求前预留响应空间，不能在收到响应后反压RAM。rd_valid一拍脉冲；没有新请求可保持data但不再次消费。最后word低N%8 lane有效（整8则ff）。group=word>>4，指数由同沿同步指数RAM读取。Stage5不打包512bit，不生成TUSER。
