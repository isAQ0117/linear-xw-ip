# Stage6 Result Buffer读取接口

本文件只冻结Stage5内部读接口，不实现AXIS sender、512bit打包RTL、TUSER或Job Status。

| 端口 | 方向 | 语义 |
|---|---|---|
| job_results_ready | 输出 | 当前Job所有Group已最终提交并publish；保持到retire/reset/abort/error |
| rd_req | 输入 | 请求valid；可提前保持，只有与rd_ready同沿才接受 |
| rd_ready | 输出 | 已发布且word index在0..ceil(N/8)-1；无第二个缓冲承诺 |
| rd_word_index[15:0] | 输入 | 全Job顺序Word索引，可合法随机读取 |
| rd_valid | 输出 | 请求沿后注册的一拍响应；下级在下一沿消费 |
| rd_data[143:0] | 输出 | 8个signed18，lane l位于[18*l+:18] |
| rd_exp signed[7:0] | 输出 | 与word>>4对应的Group共享指数 |
| rd_mask[7:0] | 输出 | 低连续L位有效；仅最后Word可不足8，其他为ff |
| rd_index[15:0] | 输出 | 响应所属Word索引，与数据同拍 |

请求在沿t接受，data/exp/mask/index/valid在t后可见，Stage6在t+1沿采样。可每拍请求，不提供response_ready。Stage6必须在请求前预留空间并消费全部已发响应；输出反压应先停止发请求、保留在途响应。没有新请求时rd_valid在下一沿撤销，不能把保持的数据重复消费。reset/abort/error/retire取消响应。

Group g的第s个word地址16g+s；通道=8*word+lane。M=1时这就是Row-Major。尾word的未使用lane实际写0；mask同时明确有效长度。Group之间边界恒为128个Mantissa，即16 words，不与未来每Beat28个Mantissa的边界混淆。

所有Job结果真正完成前rd_ready=0，不允许读取部分提交Job。已发布时越界rd_req是内部40错误；未发布时提前rd_req只等待ready。失败作废元数据和读授权，不逐字节清RAM。job_start只在job_ready采样，retire由未来上层在完成Stage6使用后发一拍，且clean_boundary必须为1；Stage5的JobReady不是Job Success Status。

实际预验证：tb对每个同步响应word/exp/mask/index逐bit检查；RESULT_READ JSONL来自实际RTL。tools/check_stage5_readback.py重新从这些真实读值恢复signed18数组，与两Golden核对，然后仅在测试软件中按每Group28个元素重分为512bit并解包还原。包括N129的16个满word+1个单lane尾word；没有实现正式Stage6 RTL。
