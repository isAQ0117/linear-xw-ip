# 独立源码审查 R1 修订对照

输入附件已完整读取，原文归档为INDEPENDENT_REVIEW_INPUT.md。审查状态REVIEW_NOT_ACCEPTED已接受；本轮修订后的本地测试结果不等同于独立审查者签核，**外部复审仍Pending**。

| 编号 | 源码/文档修订 | 验证 |
|---|---|---|
| P0-01 | X本地写入违例由23改为40；W的DDR写入故障仍23；周期模型和独立断言同步 | Activation全错误注入；review TB强制Parser→X index错误，检查X失效、Harness锁定及测试result_code=40 |
| P0-02 | load_done_reg保存脉冲；公开load_done组合屏蔽blocked，涵盖NBA后Receiver故障 | 实际Receiver同沿Extra Beat与S_LOADED完成；断言内部raw_done=1、range_error=21、公开done=0，下一沿fault21；无Python期望生成器 |
| P1-03 | job_begin周期ready=0，非法重复begin报40 | Parser轨迹中同周期TVALID+重复begin，检查沿前无握手、沿后fault40、无wr_valid |
| P1-04 | 明确无rd_ready、一拍响应、不保持等待，预留容量和不可预测stall适配职责 | 接口文档新增阶段4消费约束；保留连续读及脉冲周期比较，不声称阶段4保持适配器已实现 |
| 证据缺失 | 完整工程源码、Golden、模型、全部TB、Harness、构建入口、实际日志、Manifest、Diff统一打包 | ZIP CRC、逐文件哈希、目录完整性检查；sim_build由脚本重生，向量哈希记录在结果JSON |

新增tb/tb_xw_stage23_review.v采用独立手写定向激励和常量断言，覆盖真实Receiver导致的同沿故障、Reset/Abort/Loaded/Done优先级、内部X写错后的根因传播。原周期套件补充Buffer final-write与Abort/Reset冲突，Addr所有五个Burst参数的Loaded与各错误/Reset/Abort冲突。make stage23-test将同时执行新定向TB，日志为logs/review_directed_hdl.log。

原报告中678486拍为修订前结果；当前值以VERIFICATION_RESULTS.json和已更新DELIVERY_REPORT为准。未改变冻结标准、四个旧Stage1 RTL或数值算法。

本次重新自审：公开完成必须按最终组合故障屏蔽，不能只依赖FSM下一沿反应；错误归因必须按数据来源分类，不能复用W错误码到X；控制冲突不得对外宣告未被实际消费的握手。这三项此前自审漏检，本轮已以独立定向反例补测。仍需外部审查，不依据本记录自行宣布正式签核。

审查原文描述其所见ZIP含.git以及仅七文件的Stage_2_and_3.zip；本会话未提供该Stage_2_and_3.zip，不能推断它与原工作目录一致。本轮完整包以实际清单/哈希为依据，避免再次仅交付四个RTL。旧ZIP历史差异不作为修改冻结标准的理由。

复测实测：43/43软件通过；16组真实HDL周期轨迹共678659拍通过；独立手写审查TB通过。将两项P0分别恢复为旧错误行为的临时RTL突变，独立TB均正确报FAIL；证据见logs/review_mutation_hdl.log。临时突变只在忽略目录sim_build中，不属于交付生产源码。
