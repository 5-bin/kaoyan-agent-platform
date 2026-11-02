# 知识与学情回答可信度修复验证（2026-11-02）

本轮按用户确认的“整段降级、规则事实＋AI分段”实施前三项审查问题。业务契约维护于[搭建文档](../考研Agent平台搭建文档.md#回答可信度修复契约2026-11-02)，引用字段与兼容说明见[RAG契约](rag.md#引用支持度2026-10-24)。本报告仅记录本轮实现、实际离线检查与限制。

## 实现与复现结果

| 场景 | 修复后的行为与实际检查 |
| --- | --- |
| 正确claims遗漏正文“TCP默认端口99999” | 正文覆盖失败，整段AI降级为来源摘要；遗漏短句、变更否定词、调换顺序也拒绝 |
| 短claim和来源数字子串 | 短claim不再跳过；来源61不支持1、6或6.1，按完整数值核对 |
| 正常完整回答及Markdown列表／加粗／合法引用标记 | 正文与claims对应时保留AI解释；旧无claims的有依据回答继续兼容 |
| 快照12次、正确5次，问题／历史带1000题和98% | 最终保留代码生成的12次、5次，拒绝旧自由回答和个人统计解释，数字不会从问题升级为事实 |
| 有公开来源但解释无依据，或用线程资料解释TCP | 无论上下文是否裁剪都逐条检查自己的可见来源；任一失败丢弃全部AI分段 |
| 合法解释＋非法建议 | 整段降级，已通过的概念解释也不采用，不产生业务操作 |
| 合法解释、作答回顾、概念复习与相关练习建议 | 规则事实与AI解释共同展示；建议文案由代码生成，回顾要求已提交、可用、带版本及答案的快照，练习仍需预览确认 |
| 统计61次／正确17次及错误次数 | 正确率27.9%、区间错误44次及知识点错误11次由代码展示，保留区间与画像的不同口径 |
| 仅授权错题，未授权统计 | 未授权统计仅用于本人本地展示，不进入模型输入；含学情的复合回答不再进行模型汇总 |
| 供应商返回部分正文后取消／超时 | 真实OpenAI SDK＋MockTransport的4个组合检查底层流关闭、每次计数1次、零正文delta |
| 真实SDK返回新学情结构 | 一次替身请求完成结构校验及规则拼接，最终公开结果没有explanations／suggestions内部字段 |
| SSE与历史 | 知识问答只展示阶段及最终结果；真实Java→Python回归验证成功保存与重新订阅不重复创建任务，历史JSON不迁移 |

解释最多5条，每条最多1000字符；建议最多5条。建议仅允许REVIEW_CONCEPT、REVIEW_ATTEMPT、COLLECT_SAMPLES、PRACTICE_RELATED。COLLECT_SAMPLES只针对本轮整体区间统计questionCount不足5次，不推断独立样本数或任意知识点样本；空evidenceRefs表示整体区间。无法定位有效证据时拒绝。旧LearningAnswer自由字段只识别并返回现有降级原因，不采用其正文。

修改位置：`kaoyan-agent/grounding.py`、`learning.py`、`agents/knowledge.py`、`agents/learning.py`、新增`agents/learning_validation.py`、`agents/results.py`、`agents/coordinator.py`、`core/runtime.py`及对应提示词。新增独立反例文件`tests/test_answer_trust.py`共32项；更新原有测试中已明确变更的协议预期，冻结的历史JSON夹具未改写。Java仅调整会话集成测试的待审增量预期，本轮未修改Java业务实现或前端代码。

## 实际验证

环境为macOS、本项目`.cache/mcp-pdf-venv`的Python 3.13；Java运行于本机JDK25.0.4.1，编译目标17。模型使用合成响应或HTTP MockTransport；Java业务库使用隔离H2，Redis使用测试替身，真实FastAPI／MCP子进程仅属于测试环境。

从项目根目录运行：

```bash
.cache/mcp-pdf-venv/bin/python -m pytest -q kaoyan-agent/tests
```

结果：**874 passed，2条依赖弃用警告，59.32秒**。包含本轮32项新增反例与成功路径、框架导入、预算、账号隔离、超时取消、MCP及历史兼容。工作树另有现存功能修改，全量数量不单独归因于本次修复。

进入`kaoyan-B`，将PYTHON_EXECUTABLE设为本项目上述Python的绝对路径后运行：

```bash
bash ./mvnw -B verify
```

本轮控制台结果：**223项，0失败、0错误、2跳过，BUILD SUCCESS，56.272秒**。其中`ConversationIntegrationTest`21项通过，`AgentChainTest`使用真实Python子进程。本机Wrapper没有执行权限，未修改文件权限，改由bash执行。2项跳过均为`ExportIntegrationTest`：未设置KAOYAN_EXPORT_REDIS_TEST，不涉及本轮修复。构建目录可能含更早的报告，不将历史XML简单累加成本轮数量。

相关文件`git diff --check`通过。提示词、搭建文档、README与RAG契约同步；新增文档链接经本地路径与锚点核对。

## 限制与未运行项

- 引用检查仍是词项重叠基线，正文覆盖保证“检查了所有输出”，不代表证明语义蕴含；同义改写可能保守降级，否定和逻辑矛盾仍不能完整识别。
- 学情概念解释禁止个人统计措辞，并仅核对自己的公开来源；模型建议只选择受限动作，服务端生成实际建议文案。新内部格式对真实供应商的遵从率未运行。
- 本轮未运行真实付费模型、真实MySQL／Redis／Qdrant、前端生产构建、浏览器页面回归或公网部署。
- 本轮未操作日常库、修改真实配置、启动／停止日常服务、提交或推送。需重新加载Python代码后生效；审查第4—7项仍留待后续处理。
