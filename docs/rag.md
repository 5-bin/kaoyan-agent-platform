# RAG与院校推荐：当前实现契约

2026-11-02：院校库查询 `SCHOOL_LOOKUP` 由Java读取业务库并保存 `schoolCatalog`，与本文审核RAG及条件推荐集合分开。已有资料可以带待核实状态展示，不因此成为推荐证据；详情局部指标失败及完整字段见[院校查询契约](../考研Agent平台搭建文档.md#院校库查询与局部加载契约2026-11-02)。

2026-11-01：模型输入增加预算及确定性裁剪，完整定义见[统一规划与执行预算契约](../考研Agent平台搭建文档.md#统一规划与执行预算契约2026-11-01)。检索语料、releaseId、候选排序及授权集合不变；只裁模型输入副本的历史、允许节选的证据正文和低优先级统计明细，来源编号、版本及资格条件不裁。生成前返回实际可见证据，已有引用支持核对使用这些摘录；未改变词项校验的能力边界，不宣称证明语义蕴含。模型长度终止或必要内容超限使用原规则结果，无追加请求。验证见[P0记录](planning-budget-scheduling-verification-2026-11-01.md)。

## 招生官网网址（2026-11-01）

招生自动取证与核验已移除：当前以[搭建文档招生官网网址契约](../考研Agent平台搭建文档.md#招生官网网址契约2026-11-01替代自动核验)为准。招生MCP仅提供本地登记网址，工具 `get_admission_links({schoolCode})`；主会话 `ADMISSION_LINKS` 及结果 `admissionLinks` 与审核语料 `references` 分开，不抓取网页、不比对资料、不改变releaseId或推荐候选。只需院校名称，登记年份不代表最新内容。旧核验记录不改写，页面及导出只显示安全登记网址，由用户确认招生年份、专业及报考条件。实现范围见下文“当前实现”小节；历史验证只在对应报告保留，不构成本轮测试结果。

历史自动核验、PDF取证和HTML诊断记录（[语义与路由](admission-semantics-verification-2026-10-30.md)、[PDF扩展](mcp-admission-pdf-verification-2026-10-29.md)、[MCP取证](mcp-admission-verification-2026-10-29.md)、[HTML诊断](admission-html-diagnostics-verification-2026-10-30.md)）均由本节及搭建文档当前契约替代；这些文件保留当时的环境、范围和限制，不再描述当前可执行能力。

当前实现：`config/admission-sources.json` 仅保留 `code/name/hosts/entries/year`；stdio子进程只加载该清单，输入严格为 `{schoolCode}`，输出严格为 `{schoolCode,schoolName,registeredYear,entryUrls}`，客户端与Java逐项核对名称、登记年份及完整有序网址。助手历史、任务历史和导出从登记院校重新投影；旧`admissionCheck`中的正文、状态、差异、摘录、哈希、核验时间、基线和限制不再展示或进入模型历史。旧记录仍以原JSON保存，无数据库迁移。

范围维护已扩展到院校库121校；逐校来源、3校主页导航及访问限制见[官网登记清单](admission-source-catalog-2026-11-01.md)。这是链接范围扩展，不改变审核RAG、releaseId或规则推荐候选；生效与验证状态见README及本轮验证记录。

实际检查及未运行项见[2026-11-01验证记录](admission-links-verification-2026-11-01.md)。单次本地查询限时5秒；下文招生12秒与PDF预算只属于旧实现。

## 招生PDF扩展（2026-10-29）

招生实时证据可选format为html（旧记录默认）或pdf；PDF必须携带pageNumber（1—60文件页序）和bbox（x0,top,x1,bottom，有限非负数、正面积），HTML不得携带页码或坐标。PDF hash按原始字节计算；年份须来自同页可见内容，不继承文件名、元数据或其他页条件。完整表格才比对，相关自由文本仅形成UNREVIEWED证据；仍不进入正式references或RAG。下载及解析限额、取消和失败规则以搭建文档PDF增量契约为准；实际范围见[PDF扩展记录](mcp-admission-pdf-verification-2026-10-29.md)。

## MCP调用可靠性（2026-10-30）

知识和招生MCP分别隔离生命周期及连接故障；状态、健康字段、错误分类、关闭和无自动恢复规则统一见[搭建文档](../考研Agent平台搭建文档.md#阅读导航)。知识检索每轮共享最多3次、单次5秒，招生共享最多1次、总计12秒；参数非法或连接不可用不占调用预算，实际提交的失败／超时仍计入。工具业务无结果与结果校验失败保留连接并明确分类，断连后不继续发送。GET /health新增mcpTools，不通过探测工具或联网获取状态；现有字段兼容。检索证据、版本、来源及64KiB上限保持原校验。

## 招生实时取证（2026-10-29）

2026-10-30补充（历史）：HTML取证支持受控学位分节与明确组合列；摘录保留分节、表头、原始行及必要跨行结构，供MCP客户端按相同规则复核。同一基线五字段SAME且无实质限制为CONSISTENT，方向错位／混合方式不生成比较；范围免责声明固定展示，不阻断一致状态。完整处理当前页面／PDF并取得五字段唯一值后停止抓取，导航无表仅作诊断。诊断独立于公开结果且默认关闭，DNS拒绝与取得HTML后的解析失败分别记录。旧增量契约保留在[搭建文档阅读导航](../考研Agent平台搭建文档.md#阅读导航)；当前入口见[README](../README.md#可选招生官网链接-mcp)，历史解析验证见[解析记录](admission-html-diagnostics-verification-2026-10-30.md)。

历史（2026-10-29）：默认关闭`ADMISSION_MCP_ENABLED`，显式官网查询经独立招生MCP工具执行；普通推荐及知识MCP不变。基线只能来自本次加载的同年school资料。实时结果位于`admissionCheck`，带query、baselineReleaseId、checkedAt、status、limitations、evidence及comparisons；证据包括链接、定位、必要摘录、获取时间、未知可空公告日期与SHA256，差异绑定原资料编号与本次证据编号。完整条件且可解析的字段才比较，缺失不等于删除，未发现不等于停招。实时证据不进入审核语料references或索引，不改变当前releaseId。Java按受控来源映射和白名单结构校验保存；沿用本人任务历史及保留期，不新增在线发布。实际范围见[招生MCP记录](mcp-admission-verification-2026-10-29.md)。

## 可选只读MCP检索（2026-10-29）

`KNOWLEDGE_TOOL_TRANSPORT`只接受`local`（默认）或`mcp_stdio`，与`RAG_BACKEND`独立。MCP模式通过受FastAPI生命周期管理的固定Python子进程执行原知识检索，不改知识／招生语料、排序、分块或公开响应；题目语义索引与院校筛选不走MCP。工具`retrieve_knowledge`仅接受现有query（1—8000字符）和可选subject，禁止额外字段，固定knowledge领域和最多5项。结构化结果为`{releaseId,retrievalBackend,documents}`，Document字段保持现有定义；声明输入／输出Schema。客户端拒绝工具／Schema变化、错误结果、版本或后端不一致、重复／非当前文档、来源篡改及超过64KiB的结构化结果，不截断必要证据、不静默转本地。

每进程共享一个stdio会话；启动及发现10秒，单次调用5秒，每轮生成最多3次检索，无自动重试，原模型预算不变。最多2个同步检索工作线程，超时／取消发送对应MCP取消通知，阻止迟到结果继续使用；同步线程可能持续到本次只读检索结束，不等同于强制终止。子进程只接收检索所需配置，不加载根.env、业务库或模型凭证，不自动建索引／下载权重。MCP模式知识Qdrant由子进程独占，FastAPI退出关闭连接和子进程。异常保留现有任务失败或学情局部降级语义。实际验证结果以后续记录为准。

2026-10-29后续补充：新增40道有明确许可的计算机组成原理课程习题，学生可练习题合计404道，题目索引`questions-61a43a79e166fc054b2f3fd3d84efe12`已READY。以新增40题为授权集合的补码／Cache／中断本地检索通过，知识／招生RAG未扩容，仍为31条及原releaseId；详见[题库补充记录](data-collection/co-questions-2026-10-29.md)。下段364题是同日此前状态。

2026-10-29当前本机内容：学生可练习364题，独立题目索引`questions-6e77a4671f414f596dc4d4d158c200b9`已READY。新增的200题按内容复核后的模拟练习使用，来源归属未确认为真题。页面有36篇资料、121校797条专业，其中738条新接入专业明确标记“采集待核实”；这些招生条目及新增讲义未进入知识／招生RAG或条件推荐。该RAG仍为31条及原releaseId；下述10月24／28日数量为相应日期历史状态。实际范围与验证见[全部材料接入记录](data-collection/all-local-import-2026-10-29.md)。

2026-10-29 框架实现：模型与编排已迁移为 HelloAgents 0.2.8 项目扩展，保留本页协议、资料、索引、筛选、引用和结果校验。检索不使用框架默认 RAG 或默认上下文重筛／截断，语料内容、releaseId、候选排序和来源集合不因换框架改变；实际隔离回归及未运行范围见[本轮记录](helloagents-multiagent-verification-2026-10-29.md)。

2026-10-24本机日常数据更新：已启用31条真实来源副本（15条院校专业＋16篇四科知识摘要），版本`rag-v1-a476bf509577d904`。原`knowledge/corpus.json`仍为自动化验证的小范围基线，不与本机加载量混称。日常业务库已清理演示数据，已审核可练习题为44道数据结构课程习题；本地题目索引已重建且READY，旧题ID不在当前授权集合中。华南师范大学两条专业保留2026-10-23核验日期，本次动态目录不可访问。来源、许可、实际验证与清理影响统一见[本轮接入记录](real-data-import-2026-10-24.md)和[来源清单](real-data-sources-2026-10-24.md)。

2026-10-28采集包另新增320道待审题、20篇草稿以及院校／专业暂存记录，均未发布到学生题池或RAG；上述已发布副本不变。本批字段、审核缺口与真实数据库操作见[导入记录](data-collection/import-2026-10-28.md)。

同日后续授权：其中120道操作系统题和10篇讲义已按AI辅助复核结果发布，44条院校专业方向事实已用于页面展示。当前学生可练习题164道，本地题目索引`questions-ded53e23e92af3bff5182b02065d837b`已READY；200道待审题不进入该索引。知识与招生RAG仍为原31条及原releaseId，新讲义缺少公开原文HTTPS、新招生方向未完成推荐副本适配，不能把本次页面发布称为RAG扩容。详情及剩余核验范围见[发布记录](data-collection/publication-2026-10-28.md)。

2026-10-23新增[学情助手及隐私边界](assistant-learning-contract.md)：所有模型路径（含本文同步任务）默认拒绝未授权外发，按数据类别和接收端点校验；新任务响应不公开inputPayload，旧同步任务和聊天副本均受30天保留及主动清除规则约束。

连续聊天、HelloAgents协作、内部流式入口、会话条件覆盖和个人文档建议协议见[连续聊天契约](conversations.md)。以下同步接口及已有院校／练习入口继续兼容；聊天历史由Java从数据库组装，不接受前端伪造历史。

## 调用与数据边界

浏览器只访问Java `/api`；Java从认证会话读取账号、从数据库读取本人档案和作答，通过内部凭证调用Python。Python只读取版本化资料副本及Qdrant，不读取业务库、不接受模型生成SQL或修改业务数据。

`POST /internal/rag/chat` 使用 `X-Internal-Key`。缺失或错误凭证401；任务/字段/长度不合法422。输入含 `taskId`、正整数 `userId`、`taskType`，任务类型为 `KNOWLEDGE_QA`、`SCHOOL_RECOMMEND`、`PRACTICE_SUMMARY`、`CHAT`、`WRONG_QUESTION_TUTOR`。未知字段拒绝，消息只允许user/assistant，最多6条、每条4000字符；问题最多8000字符，错题辅导最多2000字符。

错题辅导的授权历史快照 `attempt`、父任务链、模型输出及降级规则以[搭建文档](../考研Agent平台搭建文档.md)为准。其他普通同步类型不接受非空attempt；主对话ConversationRequest可接收Java核验的attempt，仍以CHAT创建并由知识专家执行。所有请求仅通过 Java 转发；Python 不以题号读取业务库。当前辅导只使用历史作答，不生成外部来源引用。

Python响应保留 `status=SUCCESS|FAILED` 表示处理是否成功，领域终态在 `result.outcome=COMPLETED|NEEDS_INPUT|UNSUPPORTED`。不能把HTTP200或SUCCESS当成领域目标已完成。结果带 `resolvedTaskType`、`explanationMode=rules|ai|fallback`、`releaseId`、`references`；失败不回传供应商异常正文。

Java校验任务编号、版本一致性、结果结构、HTTPS来源、来源编号以及候选引用范围。任务提交没有数据库长事务，短事务先保存RUNNING，再执行远程调用，最后保存结果。单实例重启将遗留RUNNING标为失败。Redis负责注销撤销，认证还检查数据库中的当前账号状态与角色。按账号、UTC日限制30项，每分钟6项；可配置。任务分页total是真实总数。

## 推荐与历史

Java外部入口 `POST /api/recommends/generate` 接收 `{query,preferences}`，等同于向 `/api/tasks` 提交 `SCHOOL_RECOMMEND`。两者使用同一条流程和task表，不再向旧 `recommend_record` 写占位推荐。

`preferences` 支持 `majorCodes`（最多10个六位代码）、`degreeType`、`regions`（最多30个）、`regionConstraint`、`studyMode`、`examSubjects`（最多4个三位代码）、`explainWithAi`。年份由已保存档案决定。专业优先用明确的本次代码，否则匹配档案中的代码或完整专业名；学位类型依次取本次偏好、档案`degreeType`、院校库按专业代码推断（2026-11-03）；缺少年份、专业或仍无法确定学位类型时追问。自由文本是补充问题，不偷偷覆盖结构条件。

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

Qdrant检索先过滤knowledge/school领域及releaseId，并支持科目过滤，再进行向量近邻。院校硬条件在结构化副本上执行，不用相似度判断年份、专业或数值大小。knowledge问答无候选即未覆盖；可调相似度阈值，分数不是置信概率。检索后端可选`lexical`（默认词项）、`bm25`（字符n-gram轻量BM25）、`qdrant`或`hybrid`（BM25与向量RRF融合，向量索引缺失或Qdrant客户端连接／响应错误时回退BM25，2026-11-02补充后者）。知识问答会先用科目提示缩小范围，过滤后无结果再回退全语料，避免弱提示造成假“未覆盖”；结果按资料文档去重。2026-11-02修订：科目提示以明确科目名优先，其次按不重叠的提示词长词优先（“协议栈”不再被“栈”判为数据结构，ASCII词按整词匹配，“ip”不命中“pipeline”）；提示词跨多个科目时不指定科目。检索结果须提及本轮识别出的主题词，否则视为弱匹配丢弃，先放宽科目再检索，仍无结果返回`UNSUPPORTED`“当前审核资料未覆盖”，不再把无关资料标为COMPLETED。服务进程的向量检索只读本地权重（`local_files_only=True`），缺权重缓存时为检索不可用（混合模式回退BM25），不在请求中下载；权重由`ingest.py`准备。

资料修订流程：来源核对→修改资料与版本→新增回归案例→PR内容复核→离线建索引→部署对应服务版本。就绪标记必须和集合同时备份；保留旧资料与集合用于历史核对和回滚。当前不提供上传任意URL、自动抓取或管理员在线发布功能。

## 引用支持度（2026-10-24）

2026-11-02本轮信任校验契约：知识正文须被claims按顺序完整覆盖，短claim同样核对，未提供claims时核对全文；任一事实不支持、漏检或无法核验，整段AI降级。数值使用完整数值比较。内部学情输出改为explanations与类型化suggestions，统计事实由代码生成，问题／历史数字不参与统计依据；解释始终逐条对照实际可见的公开来源，建议由代码核验并生成文案。旧学情自由回答降级。学情citationSupport不包含个人记录，包含学情的复合回答本地拼接；知识问答／学情待审正文不通过delta展示。公开字段和既有降级码保持兼容，详细契约见[搭建文档](../考研Agent平台搭建文档.md#回答可信度修复契约2026-11-02)，实施与实际验证见[本轮记录](answer-trust-verification-2026-11-02.md)。

模型回答保留原有`sourceIds`白名单校验，并新增`result.citationSupport`：

| 字段 | 含义 |
| --- | --- |
| `status` | `SUPPORTED`／`PARTIAL`／`UNSUPPORTED`／`NOT_CHECKED` |
| `checked` | 参与核对的单元数：有claims时逐条计数，覆盖失败另计一项；否则按句子合并短句后计数。严格路径不跳过短结论，仅豁免固定的纯资料缺失说明 |
| `supported` | 与所引原文词项重叠达阈值的结论数 |
| `ratio` | `supported / checked`，保留三位小数 |
| `unsupported` | 最多10条未充分对齐的结论及原因（`low_overlap`／`number_mismatch`／`unknown_source`等） |
| `items` | 最多20条逐条结果：`text`、`sourceIds`、`supported`、`ratio`、可选`reason`；供页面展示 |

知识问答的模型输出包含可选`claims[{text, sourceIds}]`（最多10条）。每条claim只与自己的来源核对，正文与claims在忽略排版及合法引用标记后必须完整且顺序一致，数字和否定词保留。未知编号或正文覆盖失败整体降级。旧无claims格式仍核对全文，短句不能绕过检查；正文不增加未列入claims的引言或事实。

知识问答及学情解释要求每个核对单元都通过，部分通过与无法核验均整段降级；严格报告混合通过时为`PARTIAL`，不将80%通过当作全文可信。院校解释和通用聚合继续保留≥0.8为`SUPPORTED`、≥0.5为`PARTIAL`的原有比例口径，本轮未改院校采用策略。没有学情的复合请求仍可按原预算尝试综合解释；有学情时固定本地拼接，个人规则事实不再进入二次改写。修复前曾有一次DeepSeek学情＋3天计划＋综合解释验证（17.2秒），仅保留为当时环境的历史证据。

2026-11-02修订：未按句子计数时，少于10字的短句不再跳过，而是并入相邻句一起核对，避免“端口号为99。”这类短句绕过数字和词项检查。知识问答中`NOT_CHECKED`（没有可核对结论）与`UNSUPPORTED`同样降级为来源摘要。院校解释只有`SUPPORTED`／`PARTIAL`的候选采用AI文本，其余候选保留规则说明；全部未采用时`explanationMode=fallback`，部分未采用时保留`ai`并附提示。结果字段与终态不变。本次只运行了离线替身pytest（`kaoyan-agent/tests`全部通过），未运行真实模型、真实Qdrant或三端联调，不代表领域效果验收。

这是**词项重叠基线**，不是语义蕴含或事实核查：它能发现资料中没有的补充（如“三次握手”而原文只有序号/确认/重传），但不能可靠识别否定、自相矛盾或同义改写。严格路径只豁免固定的纯资料缺失说明，不能用“来源／资料未覆盖”等前缀跳过其后事实。任务结果视图已展示支持状态、比例，以及“逐条结论与来源”（引用编号映射为S1—Sn，并标记已核实/未核实）；旧客户端忽略该字段即可，不影响Java落库与SSE。

评测入口（默认离线，`--model`才使用根`.env`的真实供应商）：

```bash
.cache/helloagents-venv/bin/python scripts/eval-quality.py --output .cache/quality-report.json
.cache/helloagents-venv/bin/python scripts/eval-quality.py --model --only qa-stack,qa-tcp --output .cache/quality-model.json
.cache/helloagents-venv/bin/python scripts/eval-quality.py --backend bm25 --output .cache/quality-bm25.json
```

2026-10-24实际结果：离线`lexical`／`bm25`／`hybrid`各10例全部通过；真实模型只执行4个知识问答，终态4/4、引用命中4/4，模型返回14条claims（各例4/3/4/3）且14/14通过支持度核对。范围与限制见[质量评测记录](quality-eval-2026-10-24.md)，不能据此声称院校解释、完整408或正式领域效果已验收。

## 总结、安全与验证边界

Java在判分时把题干、标准答案、解析、版本写入作答快照。总结要求本人批次的全部valid项目已答，否则409且不创建任务。任一valid作答的快照为NULL或空对象，返回409及“该批次包含缺少题目版本快照的历史作答，暂不支持生成总结”，在创建任务和消耗额度前拒绝，不调用Agent。不静默排除旧作答，也不按当前题目补造历史。通过检查后读取全部已答且valid的快照，最多50题；withdrawn等无效作答不参与检查或统计。正确题数和正确率来自代码，模型不能覆盖。2026-11-02起：仅授权错题时只发送答错的题目快照，不发送答对题及其判分标记；统计需另有stats授权。练习总结、学情分析和复合汇总中，模型文本出现的阿拉伯数字必须已在本轮发送的数据中出现，否则降级为规则结果；该检查不识别中文数字或“全部答对”这类措辞。2026-11-02修订：按完整数值比对，不再按子串匹配（“61”不再让“1”“6”通过，“01”“1.0”与“1”视为同值）；发送数据中0～1之间的小数比值（如正确率0.2787）额外允许四舍五入到0～2位小数的百分数（28、27.9、27.87）。该检查仍不能判断数字是否属于正确的题目或统计口径。练习总结的模型输出只采用`summary`字段，供应商附加的其他字段（DeepSeek实测会返回`additional`）被丢弃、不展示，提示词同时要求只输出该字段；此前严格校验使该路径对DeepSeek始终降级，2026-11-02修复后真实请求2次均为`ai`且数字与规则统计一致。

提示词在prompts中，用户输入、历史和资料只作为user消息中的结构化数据；模型输出经Pydantic、来源白名单和词项支持度检查。支持度基线可发现部分无依据补充，但不能证明语义蕴含；仍需领域案例和人工复核。

运行说明统一使用根 `.env`；不提交凭证、数据库、索引、权重或截图。已保留上游Redis注销撤销及实时账号状态／角色检查；refresh入口仍没有登录下发refreshToken的完整闭环，认证生产验收未完成。远端CI、公网、真实MySQL、远程Qdrant和付费供应商的结果只在实际运行后记录。

## 独立功能测试语料

2026-10-23用户后续授权将公共数据合并到日常开发库。根`.env`现通过`RAG_DATA`指向仓库内`knowledge/feature-2027-corpus.json`，包含10校15专业及原4份知识短摘要；正常启动也使用此范围。原`knowledge/corpus.json`保留供基线与隔离测试，详细变更、备份和验证见[日常库合并记录](development-data-merge-2026-10-23.md)。本次未切换Qdrant、未修改模型开关或用户外发授权。

[2027独立测试环境](feature-test-environment-2027.md)从[统一院校夹具](../scripts/fixtures/feature-2027-schools.json)生成10校15专业的数据库记录与专用语料，通过已有`RAG_DATA`配置使用。原`knowledge/corpus.json`仍为小范围基线；两者不混用历史核验数量。推荐coverage根据所加载专业集合生成，不固定写“三校”。来源逐条保留，燕山大学学习方式以同年度研招网专业详情直接核验；所有人数和分数线仍未收录。独立环境脚本不自动同步日常库或发布Qdrant；本次日常接入由另行授权的合并脚本完成。

## 院校目录指标与审核资料边界（2026-11-01）

2026-11-01院校目录新增独立招生指标展示契约，实现在[本轮记录](school-metrics-verification-2026-11-01.md)。`school_admission_metric`不进入本节资料副本、`school_historical_metric`、条件推荐或Qdrant，第三方待核实数值只在院校详情展示。原15条审核专业语料的空人数与参考线保持原样；维护清单不等于已审核资料发布。日常库迁移与服务加载状态以该记录为准。

## 账号额度豁免

Java 通过数据库中的当前用户名匹配 `QUOTA_EXEMPT_USERNAME`（默认 `robin`，设为空可关闭），豁免该账号每日和分钟任务额度。内部请求新增 `quotaExempt: boolean`，默认 false，仅由 Java 根据认证账号计算，前端不可指定。Python 对豁免请求跳过每日模型调用预算，且不消耗其他账号的预算；单次请求调用上限、超时和授权检查保持有效。部署须更新并重启 Java 与 Python。


## 诊断学情聚合兼容（2026-10-25）

`ChatRequest`新增可空`learningSnapshot`，仅SCHOOL_RECOMMEND接受，字段为`profileRevision`、可空`referenceScore`（0—150）、`coverage`（0—1）、`sufficient`、`blueprintVersion`及固定false的`calibrated`。Java从本人画像构造，公开任务输入仍拒绝客户端上传。旧请求省略或传null均兼容；其他任务不得携带非空快照。推荐结果可带`resultSchemaVersion=2`及该快照，Java补充触发原因和经过审核、口径可比的历史指标比较；旧结果不倒填。

自动推荐使用Java专用后台入口，校验账号、持久配置及task配额，向Python发送`modelAllowed=false`、`explainWithAi=false`。显式AI解释请求只有同时具备profile及stats授权时才把学情快照加入模型输入；没有stats授权时只解释原有候选。画像计算、AI解释和录取概率相互独立，当前不提供录取概率或经过整卷验证的预测区间。运行开关与隔离脚本见README，实际验证另见本轮记录。
