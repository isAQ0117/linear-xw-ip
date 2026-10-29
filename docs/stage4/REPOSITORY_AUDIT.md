# Stage 4 源码准入审计

阶段4 / 子任务：开发前审计与接口设计 / IN_PROGRESS。遵守 XW-DEV-STD-001 V1.0、XW-CONTRACT-STD-001 V1.0；不改冻结规则。

两附件实际解压，ZIP CRC均通过。源码ZIP SHA256为6b9ae89373a5f2baa803bfc6dde5452f69c9dd25c80d925faa33091c14ef7237；Skill ZIP为9e364a43d7450b8ef1ff5d9c1cf8fa002a7d294948d5a28cb1e24b59dd52cdc3。目录穿越检查通过。实际HEAD b67698ac6d318518ae328ab3ae91496f5a55b039（Stage23 R1）；git fsck --full成功；122个tracked文件完整。上传工作树20个modified文件均仅CRLF/LF差异，git diff --ignore-space-at-eol为空。开发以工作树原始bytes为准，不checkout历史版本、不清洗行尾。UPLOADED_BASELINE.json给出所有122文件的原始bytes和SHA256。

已阅读全部8个生产RTL、原数值/架构模型、Stage1/23寄存器模型、独立数据Golden、测试/生成/运行脚本、全部TB与联合Harness、接口/状态/自审/独立审查R1、冻结标准。Skill的SKILL.md、参考、模板及两个检查脚本完整实读；仅使用，不安装或修改用户Skill。大型历史patch按格式/所涉源路径检查；JSON/JSONL全量解析，事件分类检查。原DDR镜像为1024B，历史周期113记录；Stage23实际事件17469记录。DOCX 19 parts CRC通过，XML全文与BASELINE_DOCX_EXTRACT.txt完全一致；技术依据以冻结Markdown为准。

历史FINAL_SOURCE_MANIFEST中20个哈希失配均对应上传CRLF，LF规范化后与HEAD一致；旧SOURCE_IMPORT/Stage1 manifests描述历史版本，不当本轮签名。各历史验证结果、日志和平台Pending按来源区分，不从旧PASS推定新核心已验证。

X真实端口：rd_req/index16→registered rd_valid/data144/exp8/mask8；W：同一拍data64/mask8；Scale：rd_req/index16→registered valid/bits32。t沿接受请求，t后响应可见，下游t+1沿采样。无response ready，不能暂停采样丢数据。B2原模块组合signed48×正signed25→signed72，exp=act_exp-9+scale_power；normal/subnormal原始数学表达式保持不动。

未发现缺失依赖。原Python仅标准库。工具最初PATH无HDL，已在本地准备Icarus11.0，Yosys探索性工具另行登记。无目标器件、Vivado、DDR平台规格；不得宣称时序收敛。Stage0/1/2/3生产RTL和冻结数值/标准均受基线哈希保护。
