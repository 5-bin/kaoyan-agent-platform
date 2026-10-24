# RAG与院校推荐：当前实现契约

2026-10-24本机日常数据更新：已启用31条真实来源副本（15条院校专业＋16篇四科知识摘要），版本`rag-v1-a476bf509577d904`。原`knowledge/corpus.json`仍为自动化验证的小范围基线，不与本机加载量混称。日常业务库已清理演示数据，题库为44道数据结构课程习题；本地题目索引已重建且READY，旧题ID不在当前授权集合中。华南师范大学两条专业保留2026-10-23核验日期，本次动态目录不可访问。来源、许可、实际验证与清理影响统一见[本轮接入记录](real-data-import-2026-10-24.md)和[来源清单](real-data-sources-2026-10-24.md)。

2026-10-23新增[学情助手及隐私边界](assistant-learning-contract.md)：所有模型路径（含本文同步任务）默认拒绝未授权外发，按数据类别和接收端点校验；新任务响应不公开inputPayload，旧同步任务和聊天副本均受30天保留及主动清除规则约束。

连续聊天、LangChain、内部流式入口、会话条件覆盖和个人文档建议协议见[连续聊天契约](conversations.md)。以下同步接口及已有院校／练习入口继续兼容；聊天历史由Java从数据库组装，不接受前端伪造历史。

## 调用与数据边界

浏览器只访问Java `/api`；Java从认证会话读取账号、从数据库读取本人档案和作答，通过内部凭证调用Python。Python只读取版本化资料副本及Qdrant，不读取业务库、不接受模型生成SQL或修改业务数据。

`POST /internal/rag/chat` 使用 `X-Internal-Key`。缺失或错误凭证401；任务/字段/长度不合法422。输入含 `taskId`、正整数 `userId`、`taskType`，任务类型只有 `KNOWLEDGE_QA`、`SCHOOL_RECOMMEND`、`PRACTICE_SUMMARY`、`CHAT`。未知字段拒绝，消息只允许user/assistant，最多6条、每条4000字符；问题最多8000字符。

Python响应保留 `status=SUCCESS|FAILED` 表示处理是否成功，领域终态在 `result.outcome=COMPLETED|NEEDS_INPUT|UNSUPPORTED`。不能把HTTP200或SUCCESS当成领域目标已完成。结果带 `resolvedTaskType`、`explanationMode=rules|ai|fallback`、`releaseId`、`references`；失败不回传供应商异常正文。

Java校验任务编号、版本一致性、结果结构、HTTPS来源、来源编号以及候选引用范围。任务提交没有数据库长事务，短事务先保存RUNNING，再执行远程调用，最后保存结果。单实例重启将遗留RUNNING标为失败。Redis负责注销撤销，认证还检查数据库中的当前账号状态与角色。按账号、UTC日限制30项，每分钟6项；可配置。任务分页total是真实总数。

## 推荐与历史

Java外部入口 `POST /api/recommends/generate` 接收 `{query,preferences}`，等同于向 `/api/tasks` 提交 `SCHOOL_RECOMMEND`。两者使用同一条流程和task表，不再向旧 `recommend_record` 写占位推荐。

`preferences` 支持 `majorCodes`（最多10个六位代码）、`degreeType`、`regions`（最多30个）、`regionConstraint`、`studyMode`、`examSubjects`（最多4个三位代码）、`explainWithAi`。年份由已保存档案决定。专业优先用明确的本次代码，否则匹配档案中的代码或完整专业名；缺少年份、专业或学位类型时追问。自由文本是补充问题，不偷偷覆盖结构条件。

硬筛选：年份、专业、学位、明确的学习方式和考试科目、required地区。preferred地区用于排序；同分按资料记录更新时间降序及programId升序。最多5个候选。首批记录均有完整基本字段；字段缺失的记录不允许进入这批已核验资料。未核验资料不导入正式索引，因此当前unverifiedCandidates为空。

不自动改换年份或放宽条件；不使用本科层次或自评成绩推断录取机会。结果保留资格等待确认事项。模型仅解释固定候选，返回编号和引用必须完全对应；无效输出整体放弃，保留规则说明。

`GET /api/recommends` 返回本人最近100个未删除的择校任务（包含失败与未覆盖）；更多历史通过 `/api/tasks?pageNum=...&pageSize=...` 查询。删除路径 `/api/recommends/{taskId}` 使用字符串任务编号，只能删除本人、SUCCESS／FAILED的推荐任务；成功仍返回原有200包装。删除仅写内部deleted_at，任务及结果保留，继续计入每日／分钟额度。两种历史及分页total均排除已删除记录；已删除详情、跨账号、重复删除及非推荐删除返回404，未结束任务返回409。deleted_at不加入公开响应，不使用全局逻辑删除改变配额查询。部署前执行一次尚未应用的V8迁移。旧接口返回的RecommendRecord数组已替换成Task，前端封装同步升级；旧占位表保留但不作为新历史。

## 资料与索引

### 引用来源策略

Java聊天及同步任务统一校验引用来源，唯一配置源为[`config/reference-hosts.json`](../config/reference-hosts.json)，格式为`{"allowedHosts":["github.com"]}`（仅为格式示例）。当前清单共15个域名，覆盖真实语料的12个及旧演示语料独有的3个。Python默认读取仓库文件，Java通过Maven资源配置打包同一源文件；自动化测试核对打包资源和源文件逐字节一致。

可用`RAG_SOURCE_POLICY_FILE`为两端指定同一个绝对路径文件，完整替换默认清单。只接受非空字符串域名列表，不接受URL、端口、通配符或额外字段；大小写统一转小写，精确匹配，不隐式允许子域名。配置缺失／损坏／为空时拒绝启动，不回退旧集合；Python服务及`ingest.py`在创建检索器／索引前逐条核对语料来源。Java在原有结构校验后检查来源，保留HTTPS、无凭证URL、引用字段、编号、候选范围及releaseId一致性检查。配置变更不参与语料checksum，不改写已有releaseId、索引或历史结果。

新增资料域名需先核对来源和许可、更新共享清单并补充语料回归，再重建Java及加载两端版本；外部文件模式也需要重新加载服务。清单由维护者审核，不从待加载语料自动放行域名。Java默认打包副本和Python默认文件随同一次交付更新，单独替换其中一端不保证一致。域名获准不等于来源内容正确或引用支持结论。

`knowledge/corpus.json` 当前含4段408短摘要与6个院校专业摘要。每段保存来源、定位、版本、核验日期、许可说明和状态。它是小范围已核对来源的初始资料，尚需小组复核内容，不是完整教材、题库或全国院校数据。

2027院校来源：

- [南京审计大学目录](https://gs.nau.edu.cn/2026/0920/c4397a161925/page.htm)
- [国科大计算机学院目录](https://admission.ucas.edu.cn/info/ZhaoshengDanweiDetail/9e780c52-baf5-4020-b453-bc4510579559/8008612027)
- [中国传媒大学目录](https://yz.cuc.edu.cn/2026/0930/c8550a274510/page.htm)

只整理普通全日制081200/085404的代码、学位、科目等事实，未复制整页或教材全文，未填入计划人数、历史分数线、报录比。`updatedAt`是本项目记录核验日期，不冒充官方公告发布日期。

语料使用规范化JSON的SHA256生成releaseId，换行符不会改变版本；按450字符切块、350字符步长，保留原文定位。Qdrant集合名绑定语料checksum和Embedding模型；完成全部写入后原子发布就绪标记。不修改旧版本集合。

Qdrant检索先过滤knowledge/school领域及releaseId，并支持科目过滤，再进行向量近邻。院校硬条件在结构化副本上执行，不用相似度判断年份、专业或数值大小。knowledge问答无候选即未覆盖；可调相似度阈值，分数不是置信概率。检索后端可选`lexical`（默认词项）、`bm25`（字符n-gram轻量BM25）、`qdrant`或`hybrid`（BM25与向量RRF融合，向量索引缺失时回退BM25）。知识问答会先用科目提示缩小范围，过滤后无结果再回退全语料，避免弱提示造成假“未覆盖”；结果按资料文档去重。

资料修订流程：来源核对→修改资料与版本→新增回归案例→PR内容复核→离线建索引→部署对应服务版本。就绪标记必须和集合同时备份；保留旧资料与集合用于历史核对和回滚。当前不提供上传任意URL、自动抓取或管理员在线发布功能。

## 引用支持度（2026-10-24）

模型回答保留原有`sourceIds`白名单校验，并新增`result.citationSupport`：

| 字段 | 含义 |
| --- | --- |
| `status` | `SUPPORTED`／`PARTIAL`／`UNSUPPORTED`／`NOT_CHECKED` |
| `checked` | 参与核对的结论数：模型给出`claims`时按claim计数，否则按句子计数（少于10字、来源说明类句子跳过） |
| `supported` | 与所引原文词项重叠达阈值的结论数 |
| `ratio` | `supported / checked`，保留三位小数 |
| `unsupported` | 最多10条未充分对齐的结论及原因（`low_overlap`／`number_mismatch`／`unknown_source`等） |
| `items` | 最多20条逐条结果：`text`、`sourceIds`、`supported`、`ratio`、可选`reason`；供页面展示 |

知识问答的模型输出新增可选`claims[{text, sourceIds}]`（最多10条）。模型给出claims时，每条claim只与自己的`sourceIds`对应原文核对，而不是与全部引用一起核对；claim引用了本次资料之外的编号会整体拒绝并降级。未给出claims的旧格式仍按句子对全部引用核对，保持兼容。提示词要求claims按answer结论顺序列出，范围说明和资料缺失说明不作为claim。

判定阈值：比例≥0.8为`SUPPORTED`，≥0.5为`PARTIAL`，否则`UNSUPPORTED`；不少于10字的句子才计入。知识问答中`UNSUPPORTED`会降级为原有来源摘要，不让未对齐的模型回答替换确定性结果；`PARTIAL`保留模型回答并附提示。院校解释逐候选核对并汇总，只提示、不改变规则候选。

这是**词项重叠基线**，不是语义蕴含或事实核查：它能发现资料中没有的补充（如“三次握手”而原文只有序号/确认/重传），但不能可靠识别否定、自相矛盾或同义改写；资料未覆盖类免责句会被跳过。任务结果视图已展示支持状态、比例，以及“逐条结论与来源”（引用编号映射为S1—Sn，并标记已核实/未核实）；旧客户端忽略该字段即可，不影响Java落库与SSE。

评测入口（默认离线，`--model`才使用根`.env`的真实供应商）：

```bash
.cache/chat-venv/bin/python scripts/eval-quality.py --output .cache/quality-report.json
.cache/chat-venv/bin/python scripts/eval-quality.py --model --only qa-stack,qa-tcp --output .cache/quality-model.json
.cache/chat-venv/bin/python scripts/eval-quality.py --backend bm25 --output .cache/quality-bm25.json
```

2026-10-24实际结果：离线`lexical`／`bm25`／`hybrid`各10例全部通过；真实模型只执行4个知识问答，终态4/4、引用命中4/4，模型返回14条claims（各例4/3/4/3）且14/14通过支持度核对。范围与限制见[质量评测记录](quality-eval-2026-10-24.md)，不能据此声称院校解释、完整408或正式领域效果已验收。

## 总结、安全与验证边界

Java在判分时把题干、标准答案、解析、版本写入作答快照。总结要求本人批次的全部valid项目已答，否则409且不创建任务。任一valid作答的快照为NULL或空对象，返回409及“该批次包含缺少题目版本快照的历史作答，暂不支持生成总结”，在创建任务和消耗额度前拒绝，不调用Agent。不静默排除旧作答，也不按当前题目补造历史。通过检查后读取全部已答且valid的快照，最多50题；withdrawn等无效作答不参与检查或统计。正确题数和正确率来自代码，模型不能覆盖。

提示词在prompts中，用户输入、历史和资料只作为user消息中的结构化数据；模型输出经Pydantic、来源白名单和词项支持度检查。支持度基线可发现部分无依据补充，但不能证明语义蕴含；仍需领域案例和人工复核。

运行说明统一使用根 `.env`；不提交凭证、数据库、索引、权重或截图。已保留上游Redis注销撤销及实时账号状态／角色检查；refresh入口仍没有登录下发refreshToken的完整闭环，认证生产验收未完成。远端CI、公网、真实MySQL、远程Qdrant和付费供应商的结果只在实际运行后记录。

## 独立功能测试语料

2026-10-23用户后续授权将公共数据合并到日常开发库。根`.env`现通过`RAG_DATA`指向仓库内`knowledge/feature-2027-corpus.json`，包含10校15专业及原4份知识短摘要；正常启动也使用此范围。原`knowledge/corpus.json`保留供基线与隔离测试，详细变更、备份和验证见[日常库合并记录](development-data-merge-2026-10-23.md)。本次未切换Qdrant、未修改模型开关或用户外发授权。

[2027独立测试环境](feature-test-environment-2027.md)从[统一院校夹具](../scripts/fixtures/feature-2027-schools.json)生成10校15专业的数据库记录与专用语料，通过已有`RAG_DATA`配置使用。原`knowledge/corpus.json`仍为小范围基线；两者不混用历史核验数量。推荐coverage根据所加载专业集合生成，不固定写“三校”。来源逐条保留，燕山大学学习方式以同年度研招网专业详情直接核验；所有人数和分数线仍未收录。独立环境脚本不自动同步日常库或发布Qdrant；本次日常接入由另行授权的合并脚本完成。

## 账号额度豁免

Java 通过数据库中的当前用户名匹配 `QUOTA_EXEMPT_USERNAME`（默认 `robin`，设为空可关闭），豁免该账号每日和分钟任务额度。内部请求新增 `quotaExempt: boolean`，默认 false，仅由 Java 根据认证账号计算，前端不可指定。Python 对豁免请求跳过每日模型调用预算，且不消耗其他账号的预算；单次请求调用上限、超时和授权检查保持有效。部署须更新并重启 Java 与 Python。
