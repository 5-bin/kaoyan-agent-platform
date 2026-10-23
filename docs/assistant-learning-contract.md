# 学情助手增量契约

Java独占归属校验与业务写入。Python不访问业务库。以下新增字段可选，旧任务类型不变。

## 输入

### 2026-10-23 个人笔记与题目引用修复

- 个人笔记独立页面为`/notes`，沿用`/api/personal-documents`、版本与`documentProposal`协议；公共备考资料不变。创建／修改笔记意图优先于学情分析，`reads`可以同时读取错题或统计作为草稿材料。生成只产生建议，确认后保存；过期版本409，保留用户编辑。按薄弱点改进计划允许生成综合复习计划，在差异预览中核对科目变化。
- 聊天请求新增可选`referenceTaskId`，绑定同账号、同会话、30天内SUCCESS的来源回答。Q别名属于来源回答，不能用新读取的收藏列表重新编号解释；未指定来源时查找最近包含所需题目证据的有效回答。明确页面选中优先用于“这道题”，显式Q引用和“刚才／其”使用来源回答；歧义时返回候选，禁止猜测。
- 内部plan新增可选`knowledgePoint`（1—255字符）。Java先按真实题目／历史快照知识点过滤再截取20条；引用映射与展示证据一致。相关练习继承可信来源中的主题，只抽取同知识点的已发布题，缺题显示实际数量，零题不创建操作。
- 单题明确收藏成功后由Java给出执行结果；其余写操作继续确认。错题本成员与最近一次作答正误分别表达，不将已做对的保留错题标记说成当前答错。新增字段均可选，不新增表或迁移，不改写历史聊天。
- 来源回答的隐私类别随题目引用和主题派生结果继承；用未获本轮外发授权的私人主题筛选公开资料时，本轮仅返回本地结果，禁止借公开资料间接外发该主题。

聊天发送可带`pageContext`：`page=wrong|favorite|stat|documents|practice`，可选`subject,from,to,sessionId,documentId,selectedQuestionIds,visibleQuestionIds`。编号仅Java使用，模型侧转换为Q1/D1等别名。

`POST /internal/rag/conversation/plan`接收ConversationRequest；返回`action,standaloneQuery,conditionPatch,clarification,reads,operation,target,questionRefs,subject,difficulty,count,from,to,ordinal`。action仍支持KNOWLEDGE_QA/SCHOOL_RECOMMEND/DOCUMENT_CREATE/DOCUMENT_UPDATE/CHAT，并增加LEARNING_ANALYSIS。reads为wrong/favorite/stats/practice/documents的子集。operation为NONE/FAVORITE_ADD/FAVORITE_REMOVE/WRONG_REMOVE/PRACTICE_CREATE；target为selected/visible/wrong/favorite/normal。difficulty为EASY/MEDIUM/HARD；count默认5，范围1—50；ordinal可选，表示可见列表从1起的序号。questionRefs仅本轮Q别名，最多50个。

ConversationRequest增加`privacy={modelAllowed:boolean,scopes:string[],version:int,provider?:string}`、可选`preparedPlan`及`learningContext`。privacy缺失按modelAllowed=false；provider缺失或与当前接收端点不一致时禁止外发。scopes取wrong/favorite/stats/profile/document。基础模型授权另由modelAllowed表示。所有模型路径均遵守该字段。

## Java学习工具边界

主题筛选区分来源与操作目的。例如“将我错题本中涉及tcp协议内容的部分加入我的收藏”使用`reads=[wrong]、target=wrong、operation=FAVORITE_ADD、knowledgePoint=TCP`，不合并收藏池，也不继承其他页面的选中题目、科目或批次。明确集合请求直接读取当前本人集合；显式Q编号、序号和跨轮指代继续绑定原回答。主题忽略大小写和空白，支持TCP／传输控制协议、UDP／用户数据报协议别名，父主题匹配知识点子主题（TCP可匹配TCP拥塞控制、TCP序号）；英文按字母数字边界匹配，ATCP、TCPIP不视为TCP。完整子主题条件保留，不自动退回父主题；仅按知识点匹配，不从答案或解析扩大操作范围。未识别或多主题条件进入澄清，可用“知识点：主题名称”显式指定，不能忽略条件后操作整本。

读取、预览及当前版本复核使用相同主题比较；历史展示仍保留作答快照。多题收藏先展示PENDING预览，确认后执行；零匹配不产生操作。匹配超过50题时只预览前50题并明确总量及未纳入数量，用户可缩小范围处理其余题目，不声称已收藏全部。需求或目标不明确时说明缺少的条件，并附“推荐问法”及可套用示例；示例不参与意图授权或自动执行。所有澄清分支清除读写计划，不产生操作。

`AssistantLearningService.read(owner,plan,pageContext)`返回`{items:[...],statistics:{...},documents:[...],evidence:[...],total,readCount,scope}`，按需省略字段。items对模型使用ref，不含真实主键；Java证据保留资源编号。Java负责在外发前投影并按授权剔除。

`AssistantLearningService.finalizeActions(owner,conversationId,taskId,plan,pageContext,learningContext)`在生成成功的短事务调用，返回actions列表；每任务最多一个action。`actions(owner,taskId)`读取最新状态，`confirm(owner,conversationId,actionId)`和`dismiss(...)`用于后续确认。action公开字段为id,type,status,title,count,targets,requiresConfirmation,result；练习另带requestedCount。targets包含Java固定的题干节选和站内资源，供确认前核对对象。状态PENDING/SUCCESS/DISMISSED/FAILED；result可带sessionId/actualCount。

action表为assistant_action：id VARCHAR(36),user_id BIGINT,conversation_id VARCHAR(36),task_id VARCHAR(36) UNIQUE,operation VARCHAR(32),status VARCHAR(20),payload_json LONGTEXT,result_json LONGTEXT,created_at/updated_at TIMESTAMP。payload只在Java内部。确认执行前必须检查归属、30天有效期、源任务SUCCESS及资源状态。过期/清除删除目标内容。

## 隐私与界面

GET/PUT /api/privacy/settings：`{modelAllowed,scopes,version,provider,retentionDays:30}`；PUT提交`{modelAllowed,scopes,provider}`，provider必须与当前配置相同。首次全部关闭。provider是Python健康接口返回的安全接收端点标识，不含凭证。更新撤销取消在途生成。

DELETE /api/conversations/{id}清除单会话；DELETE /api/conversations清除全部助手聊天。原始作答、标记和个人文档独立保留。

结果evidence元素含`ref,kind,title,locator,version`及可选`resource={type:question|document|practice|stats,id}`；模型不生成任意导航URL。actions、evidence由Java最终替换为可信结果。

统计接口新增`GET /api/stats/learning?from&to&subject`，返回questionCount/correctCount/uniqueQuestions/wrongCount/accuracy、daily、knowledgePoints、from/to；仅有效已提交作答。默认上海日期近30天（包含今天）。

创建练习请求扩展source=NORMAL|WRONG|FAVORITE和可选questionIds；保留原subject/difficulty/count，count上限50。新批次创建时固定快照，不能向未答DTO泄露答案。

学习分析使用已授权的题目／聚合主题检索现有版本化408语料，最多5段公开资料；未授权私人主题不能间接用于模型检索上下文。模型LearningAnswer可返回evidenceRefs及sourceIds（最多5个），来源只能来自本次检索集合，非法编号回退本地摘要。平台已发布资料单独按Java正文定位和摘要哈希留证，不伪造教材页码。


## 执行、授权与留存

单题明确收藏自动执行，其余操作先确认；分析、否定、用法询问和引号中的示例不授权修改。Java成功终态与自动收藏同事务；确认持账号锁，核对当前登录撤销标识、原授权版本、源任务成功状态和资源快照。重复确认返回原结果。题目状态变化409；跨账号404；每任务最多一个操作。

模型接收端点以HTTPS scheme、host、port和path规范化，不含凭证、query和fragment。新授权全部关闭，授权版本改变取消相关在途聊天。旧同步CHAT仅本地识别意图，内容最多调用一次模型；完整会话plan和stream之间由Java重新检查，Python每次调用前核对授权端点。隐私撤回不追溯收回已发送数据。

已发布资料可以本地读取。错题、收藏、统计、档案和个人文档分别授权；模型不见业务主键。统计优先聚合，完整档案background不默认外发。个人文档仍需逐份选择。混合查询逐条按真实来源分类，未授权的记录及其总量不进入模型；历史和派生回答继承数据类别，撤回后不进入后续模型上下文。

原始消息、模型上下文和答案自创建起保存30天。历史只存引用，发送时读取尚未过期的授权历史；展开检索词仅本轮内存使用，不额外持久化旧问题。聊天内容不复制到task.input_payload。启动、每小时和读取/确认时执行过期检查，旧同步任务及已隐藏推荐的输入输出也按30天清理。

清除全部助手记录同时清除旧同步任务中的内容副本，保留额度计数所需元数据；清除单会话限定该会话。清除和任务完成使用账号锁及条件终态更新，取消生成且禁止迟到响应写回。原始作答、收藏、错题标记和已确认个人文档不随聊天删除。清除在线数据不代表独立备份或供应商副本已同步清除。

## 页面与验证入口

相关页面共享唯一聊天组件，桌面侧栏440px，窄屏全屏；学情与会话编号仅存账号内存。页面上下文只携带编号/筛选，不携带浏览器正文。结果导航由固定路由构造，Markdown只允许本轮来源完整URL，不加载远程图片。统计页面直接使用stats/learning，默认上海日期近30天，正确率0—1，零样本accuracy=null。

运行前在既有V11基础上受控执行一次V12；本次只提供脚本，不自动迁移日常库。验证命令沿用README的Java verify、Python pytest和前端build；`scripts/check-chat-migrations.py`在禁用网络的临时MySQL检查V10—V12，`scripts/smoke-chat.py --learning --output <新的报告路径>`在独立H2、Redis和供应商替身上检查实际页面与Java/Python链路。测试夹具拒绝日常数据库，不读取用户浏览器资料。
