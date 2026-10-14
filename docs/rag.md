# RAG与院校推荐：当前实现契约

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

`GET /api/recommends` 返回本人最近100个择校任务（包含失败与未覆盖）；更多历史通过 `/api/tasks?pageNum=...&pageSize=...` 查询。删除路径 `/api/recommends/{taskId}` 使用字符串任务编号，只能删除本人、已结束的推荐任务。旧接口返回的RecommendRecord数组已替换成Task，前端封装同步升级；旧占位表保留但不作为新历史。

## 资料与索引

`knowledge/corpus.json` 当前含4段408短摘要与6个院校专业摘要。每段保存来源、定位、版本、核验日期、许可说明和状态。它是小范围已核对来源的初始资料，尚需小组复核内容，不是完整教材、题库或全国院校数据。

2027院校来源：

- [南京审计大学目录](https://gs.nau.edu.cn/2026/0920/c4397a161925/page.htm)
- [国科大计算机学院目录](https://admission.ucas.edu.cn/info/ZhaoshengDanweiDetail/9e780c52-baf5-4020-b453-bc4510579559/8008612027)
- [中国传媒大学目录](https://yz.cuc.edu.cn/2026/0930/c8550a274510/page.htm)

只整理普通全日制081200/085404的代码、学位、科目等事实，未复制整页或教材全文，未填入计划人数、历史分数线、报录比。`updatedAt`是本项目记录核验日期，不冒充官方公告发布日期。

语料使用规范化JSON的SHA256生成releaseId，换行符不会改变版本；按450字符切块、350字符步长，保留原文定位。Qdrant集合名绑定语料checksum和Embedding模型；完成全部写入后原子发布就绪标记。不修改旧版本集合。

Qdrant检索先过滤knowledge/school领域及releaseId，并支持科目过滤，再进行向量近邻。院校硬条件在结构化副本上执行，不用相似度判断年份、专业或数值大小。knowledge问答无候选即未覆盖；可调相似度阈值，分数不是置信概率。词项基线另有中文短语与术语匹配，和向量模式明确区分。

资料修订流程：来源核对→修改资料与版本→新增回归案例→PR内容复核→离线建索引→部署对应服务版本。就绪标记必须和集合同时备份；保留旧资料与集合用于历史核对和回滚。当前不提供上传任意URL、自动抓取或管理员在线发布功能。

## 总结、安全与验证边界

Java在判分时把题干、标准答案、解析、版本写入作答快照。总结要求本人批次的全部valid项目已答，否则409且不创建任务。仅读取已答且valid的快照，最多50题；旧记录缺少快照时不编造历史依据。正确题数和正确率来自代码，模型不能覆盖。

提示词在prompts中，用户输入、历史和资料只作为user消息中的结构化数据；模型输出经Pydantic和来源白名单检查。但结构校验不能自动证明每句解释都被原文支持，仍需领域案例和人工复核。

运行说明统一使用根 `.env`；不提交凭证、数据库、索引、权重或截图。已保留上游Redis注销撤销及实时账号状态／角色检查；refresh入口仍没有登录下发refreshToken的完整闭环，认证生产验收未完成。远端CI、公网、真实MySQL、远程Qdrant和付费供应商的结果只在实际运行后记录。
