# 考研 Agent 智能备考平台

## 线上DeepSeek模型已启用（2026-11-03）

按用户要求沿用当前项目本机模型配置，服务器已开启DeepSeek，主模型和路由模型均为 `deepseek-flash`，thinking为disabled。已仅重启Python Agent并核对运行进程配置；真实HelloAgents适配层连通请求1次通过，公网首页与注册关闭检查通过。保留线上每日20次模型调用上限及账号原有隐私授权，使用个人数据须本人在对话“隐私”中授权当前供应商及相应类别。密钥不写入仓库；备份、回退及验证边界见[模型配置记录](docs/server-llm-verification-2026-11-03.md)。

## 线上OSS图片上传（2026-11-03）

服务器已配置本项目现有OSS，线上通过 `OSS_KEY_PREFIX=prod/` 与本机空前缀目录隔离。可在个人中心更换头像，图片由Java鉴权读取，不依赖公开Bucket。现有扩展名与5MB限制不变，不支持文档附件；该次OSS上线时注册和模型均保持关闭，后续模型启用状态见上方记录。

Java验证239项（2项跳过）、运维pytest103项、独立发布包启动、真实OSS上传／归属／匿名读取及公网浏览器显示和刷新均通过，测试对象已清理、test1原头像已恢复。配置／回退入口与实际证据见[本轮记录](docs/server-oss-verification-2026-11-03.md)。本机新增可选 `OSS_KEY_PREFIX` 默认空；修改配置后须重新加载Java。


## 线上测试账号与暂停注册（2026-11-03）

服务器已部署注册开关：`REGISTRATION_ENABLED=false`，已有账号可登录；匿名 `GET /api/auth/config` 只返回注册开关。页面未确认开启时不展示注册入口或表单，后端关闭时拒绝直接注册请求。其他环境默认true；恢复注册只需受控调整服务器开关并重新加载Java。

本轮已新增test1至test10学生账号，每人400次近28天模拟作答、20个结束批次、16个收藏及不同薄弱科目；不代表真实学习效果，未开启模型或额度豁免。凭证不写入仓库；一次性工具默认只读预览，正式创建／续做只认私密执行日志。分布、命令入口、备份及实际验收见[线上测试账号记录](docs/server-test-accounts-2026-11-03.md)。


## 已部署服务器的V15增量升级（2026-11-03）

`scripts/upgrade-server-release.py` 是本次Ubuntu实例的增量入口，保留首次切换工具。默认只读；需要当前／新版目录、可信运行文件清单及哈希、已通过的恢复预演与计划哈希，只有显式 `--activate` 执行维护、备份恢复预演、V15和程序切换。使用已有服务配置的精确备份回退，不重复公共资料导入；已提交V15不自动撤销。运行约定和实际结果见[增量上线记录](docs/server-release-activation-2026-11-03.md#v15增量上线2026-11-03)。 本轮已直接完成V15及新版三端切换，原字段指纹保持、公网TLS／新版首页与静态资源哈希、未认证API边界检查通过；模型仍关闭。登录后业务与真实模型未运行。


## 学情精简与档案学位类型（2026-11-03）

学情分析只列错误率最高的8个知识点（每点一行），其余汇总为一句；审核资料正文只在“查看依据”展示。个人档案新增学硕／专硕选项，院校比较依次使用本轮说明、档案、院校库按专业代码推断，不再每次追问。需先在V14后手工执行一次[V15迁移](kaoyan-B/src/main/resources/db/V15__profile_degree_type.sql)，再同时加载新版Java、Python与前端；未执行V15的库不能运行本版Java。服务器可用`scripts/prepare-server-data.py --rehearse`在隔离库预演V15（按原有核对清单），正式执行仍需另行确认。契约见[搭建文档](考研Agent平台搭建文档.md#学情精简与档案学位类型契约2026-11-03)。

## 学情补样建议修复（2026-11-03）

学情建议改为从代码生成的合法候选中选择，分别标明区间总样本、知识点区间作答及画像分组独立样本，避免总作答61次时因局部小样本误选整体补样建议而降级。裁剪上下文时同步重建候选，未知编号及非法解释仍整段拒绝；公开结果、历史兼容与模型预算保持原约定，无数据库迁移。

本轮Python全量963项通过（含新增16项回归）；已重新加载本机Agent，三端连通检查及招生MCP就绪检查通过，真实模型与登录后页面回归未运行。其他环境需按原入口重新加载Python。契约见[搭建文档](考研Agent平台搭建文档.md#学情建议候选约束修复契约2026-11-03)，范围及限制见[验证记录](docs/learning-suggestions-verification-2026-11-03.md)。

## 知识与学情回答可信度修复（2026-11-02）

知识问答核对正文与逐条结论是否完整对应，任一结论未通过则整段AI降级。学情的作答次数、区间错误次数、正确率和画像由代码生成；AI仅提供逐条核验的公开概念解释及代码生成文案的受限建议，旧自由回答降级。知识问答及学情在校验完成前只显示阶段状态，最终返回完整结果；包含学情的复合回答本地拼接，规则事实不再二次交给模型改写。

Python全量874项通过；Java verify共223项，221项通过、2项因未启用导出Redis测试而跳过。保持公开接口及历史兼容，无数据库迁移；需重新加载Python后生效。本轮未运行真实模型、真实MySQL／Qdrant、前端构建或浏览器回归，未重启日常服务。契约见[搭建文档](考研Agent平台搭建文档.md#回答可信度修复契约2026-11-02)，复现范围及限制见[验证记录](docs/answer-trust-verification-2026-11-02.md)。

## 澄清续接与AI降级原因（2026-11-02）

追问“学硕或专硕”后直接回答“学硕”等纯条件补充，按本地规则合并条件并继续择校，下一轮模型历史也包含上一轮的追问。学情回答分别注明区间作答次数与画像独立样本的口径；数字校验按完整数值比对并接受比值换算的百分数。AI 降级时结果附固定原因码 `fallbackReason`，页面在提示后显示原因（超时、服务不可用、调用次数用尽、输入过长、输出格式不符、引用未对齐、数字不一致），旧结果沿用通用提示。离线 pytest、Java verify 与前端生产构建通过；真实模型、浏览器回归和三端联调未运行，需加载新版三端后生效。契约见[搭建文档](考研Agent平台搭建文档.md#ai降级原因增量契约2026-11-02)，范围与结果见[验证记录](docs/fallback-reason-verification-2026-11-02.md)。

## 院校信息查询与详情加载（2026-11-02）

助手输入“查询北京大学招生信息”会先展示院校库已有专业、年份、招生计划和往年参考线，保留采集待核实状态、原登记备注、来源及适用口径，再附登记官网链接。年份依次采用本轮指定、个人档案报考年、该校库内最新年；目标年没有数据时说明缺口，不替换年份。聊天最多展示10条并提供完整详情入口；历史及Word／PDF／Markdown导出使用保存的查询快照。该路径由Java读取院校库，不调用模型，不依赖Python或招生MCP；“只要官网链接／核对官网”等明确链接请求保留原MCP路径。

院校详情请求15秒超时，失败后可重试；切换院校取消过期请求，无效招生指标局部隐藏并显示警告。缺V14表兼容原字段，不自动迁移。隔离MySQL、生产构建及独立Chrome检查通过；截图中的原始持续加载未在公开资料回放中复现。需加载新版Java及前端后生效，本轮未重启日常服务、修改日常数据或部署。契约见[搭建文档](考研Agent平台搭建文档.md#院校库查询与局部加载契约2026-11-02)，范围和实际结果见[验证记录](docs/school-catalog-verification-2026-11-02.md)。

独立MySQL回放沿用下方测试类路径准备，只在全新临时MySQL实例执行初始化；生产构建已准备后加`--browser`检查桌面及移动视口。输出路径须尚不存在，本机需安装MySQL服务端、客户端及Chrome；不连接日常数据库、不读取个人学习记录：

```bash
.cache/mcp-pdf-venv/bin/python scripts/smoke-school-catalog.py --browser --output .cache/new-school-catalog-report.json
```

Vue 3 / TypeScript → Spring Boot 3.5 / MyBatis-Plus / MySQL → FastAPI RAG。Redis用于JWT注销撤销，是Java业务接口的运行依赖。

## 院校招生指标维护（2026-11-01，已写入日常库）

2027计划与往年参考线的[确认清单](outputs/school-enrichment-20261101/final/preview.md)、[来源及缺口](outputs/school-enrichment-20261101/final/gaps.md)、[验证与恢复说明](docs/school-metrics-verification-2026-11-01.md)已交付。用户确认后已在`kaoyan_dev`执行V14，更新115所院校层次并新增1594条指标；[正式执行摘要](outputs/school-enrichment-20261101/final/application.json)及[日常库回读](outputs/school-enrichment-20261101/final/daily-readback.json)已保存。新表仅用于院校详情，不加入审核RAG或学情历史指标。2026-11-01后续按用户要求重启本机三端并加载新版Java；前端组件和服务健康检查通过，登录后的院校详情页面尚未实际验收。

以下从项目根目录运行，使用已安装Pydantic 2的项目Python（本次验证环境如下）。默认只读；预演完整备份并恢复到随机隔离库：

```bash
.cache/helloagents-venv/bin/python scripts/import-school-metrics.py --manifest outputs/school-enrichment-20261101/final/manifest.json
.cache/helloagents-venv/bin/python scripts/import-school-metrics.py --manifest outputs/school-enrichment-20261101/final/manifest.json --rehearse
```

只有用户确认具体影响清单后，才执行正式写入；本清单已获确认并成功执行，下方保留实际命令。入口会重新完成备份恢复、回滚及幂等预演。V14的DDL独立提交，数据事务失败可能留下空指标表。不运行V1，不自动重启服务：

```bash
.cache/helloagents-venv/bin/python scripts/import-school-metrics.py --manifest outputs/school-enrichment-20261101/final/manifest.json --apply --expected-sha 7c7a735a784174013e42ddb61f38a5b8bc2280035bd02c2d75b4a659367d78ec
```

后续新增资料须使用`prepare-school-metrics.py --help`指定新的只读快照、原工作簿、检索收据、核对观察和层次清单，输出到新目录；当前已存在指标如有任何不同会停止，不能用新批次覆盖人工修订。

当前整合同学的框架适配（上游main `6383c92`）与RAG工作流。保留实时账号状态／角色检查、Redis注销撤销、分页参数兼容和隔离HTTP检查。

本轮实现内部接口加固、408与院校独立检索副本、确定性择校、场景识别及可选LLM解释。具体协议、验收和限制见 [RAG说明](docs/rag.md)。`docs/work*.md`、`docs/agent.md` 是历史生成提示词，不是当前运行说明。

本机日常数据已于2026-10-24替换为真实来源：10校15专业、44道OpenDSA课程习题中文翻译、四科各4篇资料；演示数据及经确认的关联历史已清理。题目目前仅覆盖数据结构，非408统考真题；Agent使用31条对应语料。日常MySQL／Redis、Java8080、Agent8001及前端5173已实际连通，见下述本轮记录。

2026-10-29联网补充40道计算机组成原理课程习题，当前可练习404题（数据结构144、操作系统120、计算机网络100、计算机组成原理40），题目本地索引404题已READY。新题来自Chris Terman的Computation Structures课程，保留MIT许可、逐题来源及中文改编说明，非408统考真题；备份、发布和验证见[本次题库补充记录](docs/data-collection/co-questions-2026-10-29.md)。

同日此前全部采集材料已接入本机页面：公开资料36篇、院校121校797条专业记录。其中200题经修订后按模拟练习使用，738条专业明确标为“采集待核实”，不进入条件推荐；知识及招生RAG仍为原31条。全部可查看不代表招生事实及外部转载许可全部核实，范围、备份及真实验证见[完整采集包接入记录](docs/data-collection/all-local-import-2026-10-29.md)；[10月28日部分发布记录](docs/data-collection/publication-2026-10-28.md)保留为历史证据。

## 文档入口

- [2026-11-02提交前检查](docs/precommit-review-2026-11-02.md)：本轮三端、隔离MySQL／Redis、浏览器与MCP验证结果，修正项及公开提交边界。

> 招生官网链接契约（2026-11-01）已替代下列自动核验、PDF取证与诊断记录；历史报告保留原内容，仅作追溯，不再代表当前能力。

- [招生 MCP 仅返回网址：实现与验证](docs/admission-links-verification-2026-11-01.md)：新旧历史、三格式导出、禁网协议检查及隔离三端链路。
- [招生核验状态、停止抓取与路由修复](docs/admission-semantics-verification-2026-10-30.md)：五字段一致状态、完整取证后停止、登记范围回答与非法模型计划降级。
- [MCP调用可靠性与验证](docs/mcp-reliability-verification-2026-10-30.md)：连接故障隔离、健康状态、并发预算、错误分类与实际协议检查。
- [招生PDF取证扩展与验证](docs/mcp-admission-pdf-verification-2026-10-29.md)：文字型PDF、文件页序、隔离解析、取消回收与真实三端检查。
- [招生官网取证MCP实现与验证](docs/mcp-admission-verification-2026-10-29.md)：明确查询、同年基线比对、独立实时证据、历史保存及官网可读性限制。
- [只读资料MCP接入与验证](docs/mcp-knowledge-verification-2026-10-29.md)：真实stdio子进程、HelloAgents适配、证据校验及取消与关闭。
- [用 HelloAgents 理解当前 Agent 架构](docs/agents框架讲解.md)：框架与源码对应、六类专家、完整调用链、上下文、检索和验证边界。
- [2026-10-29计算机组成原理题库补充](docs/data-collection/co-questions-2026-10-29.md)：联网收集40道有明确许可的课程习题，中文改编、独立验算、真实导入及本机发布。
- [PR #15同步、HelloAgents适配与隐私修复](docs/pr15-helloagents-verification-2026-10-29.md)：批量导入、错题进入主助手、父任务历史及实际验证。

- [HelloAgents 多专家重构与验证](docs/helloagents-multiagent-verification-2026-10-29.md)：对话协调器、六类专家、框架分层、隔离回归及运行切换。

- [2026-10-29全部材料本机接入](docs/data-collection/all-local-import-2026-10-29.md)：剩余200题、10篇资料和738条招生记录全部可查看，包含修订、待核实标记及实际验证。
- [队员资料收集与导入规范](docs/data-collection/README.md)：5张数据表、全部985／211院校覆盖、四科各100道共400道有效题及三档难度目标；附Excel／CSV空模板和字段映射，通用批量导入器待实现。
- [2026-10-28采集包导入记录](docs/data-collection/import-2026-10-28.md)：本次Excel采集包的暂存、待审核题目与草稿资料、备份及真实MySQL验证；不自动发布招生资料或RAG。
- [2026-10-28采集包复核发布](docs/data-collection/publication-2026-10-28.md)：按后续授权发布操作系统120题、10篇讲义及44条专业方向事实，保留未核实部分与原有数据。
- [CI索引冷启动与浏览器检查修复](docs/ci-index-warmup-fix-2026-10-24.md)：等待索引就绪后仅重试一次，保留正式任务限额；浏览器测试使用生产预览，避免开发态重载。
- [引用来源与收藏主题修复验证](docs/reference-policy-fix-verification-2026-10-24.md)：共享域名策略、堆排序解析、命令跳过知识检索及固定失败码，本轮隔离验证与生效边界。
- [本机真实数据接入与清理](docs/real-data-import-2026-10-24.md)：当前日常库的10校15专业、44道真实课程习题、16篇四科资料，备份、清理范围与真实MySQL页面验收。
- [真实数据来源清单](docs/real-data-sources-2026-10-24.md)：逐题原文、版本、许可及四科资料来源；课程习题不冒称408真题。
- [完整平台搭建文档](考研Agent平台搭建文档.md)：需求、当前契约与后续建设目标。
- [框架适配历史记录](docs/当前框架适配.md)：同学在合并前的验证与限制。
- [合并审查记录](docs/merge-review-2026-10-14.md)：本次冲突处理和重新验证范围。
- [RAG详细契约](docs/rag.md)：资料、筛选、快照、引用与版本。
- [连续聊天与个人文档契约](docs/conversations.md)：HelloAgents对话协作、SSE、会话、澄清选项和文档版本。
- [个人笔记与题目引用修复验证](docs/assistant-notes-fix-verification-2026-10-23.md)：独立笔记页、复合意图、跨轮收藏及本轮验证边界。
- [学情助手与隐私契约](docs/assistant-learning-contract.md)：错题／收藏／统计／资料读取、受控操作、分类授权和30天清除。
- [学情画像可视化验证](docs/learning-profile-visualization-verification-2026-10-31.md)：统计页 KPI、知识点热力图、证据散点、补强排行、样本不足提示及移动端/数据表回退。
- [题目语义检索验证](docs/question-semantic-search-verification-2026-10-24.md)：通用主题提取、独立本地Qdrant、授权集合和真实模型限制。
- [检索质量与引用支持度验证](docs/quality-eval-2026-10-24.md)：BM25／hybrid、逐条结论引用、未核实降级、10例离线与4例真实模型结果。
- [主题筛选与澄清问法验证](docs/assistant-topic-filter-verification-2026-10-23.md)：按主题预览收藏、未知条件推荐问法及隔离链路验证。
- [院校下拉筛选验证](docs/school-options-verification-2026-10-24.md)：库内省份／专业选项接口、下拉交互及隔离真实后端验证。
- [聊天验证记录](docs/chat-verification-2026-10-22.md)：隔离验证结果与未运行范围。
- [学情与隐私验证记录](docs/assistant-learning-verification-2026-10-23.md)：三端实际链路、分类授权、清除、定向练习及隔离MySQL验证。
- [本机测试数据](docs/local-test-data-2026-10-22.md)：已写入的数据、待审核边界、备份及可重复执行的补充脚本。
- [其他功能测试数据](docs/feature-test-data-2026-10-23.md)：独立学生测试账号、模拟练习／错题／收藏／统计、任务历史及个人文档版本。
- [2026-11-03本机学情测试账号](docs/study-test-account-2026-11-03.md)：四科400次模拟作答、400条独立证据、78个样本充足分组及私密登录方式。
- [日常开发库数据合并](docs/development-data-merge-2026-10-23.md)：已合并到`kaoyan_dev`的院校、可练习题库、资料、V12及正常启动方式。
- [PR #8修复验证](docs/pr8-fix-verification-2026-10-15.md)：删除后的配额、历史快照及页面联调修复。
- [Issue #9验证记录](docs/practice-answer-safety-verification.md)：学生答案隐藏、服务端判分展示与历史回顾安全。
- [Issue #11录题与审核验证](docs/question-entry-review-verification.md)：来源登记、审核流程及V9迁移边界。
- [题库批量导入验证](docs/question-import-verification.md)：JSON预览、整批送审、重复检查和失败回滚。

## 文件导出

个人笔记可导出已保存的当前版本及历史版本，学习统计页可导出近30天统计与画像报告；成功的助手回答支持导出全文、复习计划和待确认笔记建议。点击导出先预览，再选择 Word（docx）、PDF 或 Markdown。学情报告的 Word/PDF 含图表及完整数据表。预览15分钟有效，每账号最多5份；关闭、退出或切换账号会取消前端请求。

导出由 Java 确定性生成，下载与更换格式不调用模型；需要AI分析时先通过原助手生成再导出。无需数据库迁移，使用现有Redis；重新构建并加载Java后生效。字体、依赖和真实验证见[导出验证记录](docs/export-verification-2026-11-01.md)，业务契约见[搭建文档](考研Agent平台搭建文档.md#文件导出契约2026-11-01)。

## 私有 OSS 头像

头像上传后由 Java 保存无签名地址，并通过认证接口读取本人头像，兼容旧版头像路径；新上传路径包含账号编号。OSS 未配置或读取失败时页面回退默认头像。2026-11-02起文件删除接口只能删除本人路径下的对象，当前绑定的头像需先更换；旧版无账号编号的对象无法通过接口删除。头像内容校验和孤立文件清理尚待完善。

2026-10-31 本机以独立测试账号（`feature_empty_20261023`）完成真实 OSS 上传、认证读取与浏览器显示验证：上传→保存→`GET /api/users/avatar/content` 返回字节与上传文件一致，个人中心及顶栏显示新头像，刷新后保持；本次前端生产构建通过，未使用或修改 `robin` 等日常账号。同日排查到 5173 的 Vite 进程持续返回改动前的旧模块，旧代码直接引用私有 OSS 地址，出现“提示已更新但不显示”；前端改动后需重启开发服务器并强刷页面，仅刷新浏览器不会绕过该进程缓存。头像内容仍只按扩展名校验（改名的 HEIC 等仍可能成功保存却无法显示），移动端和其他浏览器未验证。

## 当前能力

- 题库管理支持JSON批量预览与整批送审（1—50题），待审核题不进入学生题池；示例不会自动导入。
- 已判错作答可点击“到助手继续辅导”，在主对话选择错题后主动发送；支持从旧辅导任务接续、刷新恢复和清除选择。旧独立辅导面板及`WRONG_QUESTION_TUTOR`接口继续兼容，内部共用HelloAgents知识专家。诊断结束前不提供辅导，标准答案与判分不变。

- 助手支持“给我出几道有关排序的题”等自然语言组题：默认从审核题库选5题，点击“开始练习”才创建批次并直接进入刷题页；后续“继续练习”打开同一批次。题目及学习依据默认折叠，缺题展示实际数量。涉及导航功能时提供正文链接及相关入口按钮，旧聊天也可补充入口。契约见[学情助手说明](docs/assistant-learning-contract.md#助手组题与站内导航2026-10-25)，实际验证与运行范围见[本轮记录](docs/assistant-practice-navigation-verification-2026-10-25.md)。
- `/tasks` 为持久连续聊天助手，支持问答、择校、停止、最后一问重试和断线快照恢复；旧任务只读入口为`/tasks/history`。
- 学情助手可读取本人错题、收藏、有效作答统计和平台已发布资料，支持页面侧栏、单题收藏及确认后移出错题／取消收藏／创建错题或收藏练习。统计按上海日期近30天统一，未记录指标不推算。
- 外部模型默认未获用户授权；可在助手“隐私”中按类别开启并撤回，个人文档还需逐份选择。聊天及上下文30天清理，可主动清除；原始学习记录和已保存文档独立保留。V12未应用前不能运行新版Java。
- 左侧“复习”分组的`/notes`管理个人Markdown笔记，支持手动创建／编辑、预览差异及历史版本。助手可基于获授权的错题／统计生成或修改笔记，预览确认后保存；沿用个人文档API及已有版本，不新增迁移。
- 助手可按自然语言主题查找本人错题、收藏或全题库题目；合并标签与本地语义匹配，主题操作均先预览确认。首次需准备下述本地模型；短主题的语义召回仍有限，不能保证找全。
- 题目引用绑定来源回答，单题明确收藏返回Java执行结果；知识点筛选先于列表截取，相关练习不足时显示实际数量，不补入无关题。错题标记和最近作答正误分别表述。

- `/internal/rag/chat`：内部凭证认证、任务枚举、输入上限、类型化上下文、结果和引用校验。
- 408：4段带来源的概念摘要，默认离线词项检索；可启用中文Embedding＋持久化Qdrant。覆盖范围较小，未覆盖时明确返回。
- 院校：3所学校的6条2027年普通全日制081200/085404资料。按年份、专业、学位、地区、学习方式与考试科目筛选，最多5个候选；不估计录取概率。
- AI：默认关闭。启用后解释候选或回答资料覆盖的问题；模型异常时保留规则结果，来源编号经过程序校验。
- 总结：Java只传本人已判分、带题目版本快照的有效作答，Python不连接业务数据库。
- 错题辅导：答错后、回顾页或错题本点击“AI 解释与追问”，围绕同一次历史作答解释误区并连续追问；每轮保存在`/tasks/history`，可在那里继续。Java校验归属和快照并提供标准答案，模型不能更改判分。模型关闭或未授权错题外发时仅展示原题解析及明确提示；本功能无新增数据库迁移，合并后的整站仍需V10—V12。实现与验证范围见[错题辅导验证记录](docs/wrong-question-tutor-verification.md)。
- 刷题：学生抽题／详情隐藏答案；提交后展示Java判分，回顾／错题／收藏仅显示本人有效作答快照。回顾可继续作答，旧快照无选项时仍展示已保存答案；明确不可用题目提示后跳过，网络失败可重试。跳过仅影响页面导航，不修改作答或统计；旧快照缺失不按当前题目补造。
- 推荐与任务共享任务表保存快照、来源、版本和结果；历史推荐不随档案更改。
- 管理员可在`/admin/questions`录入单选题、登记来源和使用权限、查看详情、补充未发布题并通过或驳回。新题先待审核；真题必须登记年份和原题号。支持对已审核题目停用和重新启用，保留题目与历史作答；编辑、审核及启停均校验版本，过期请求409。批量导入后续建设；V13启用后可通过管理API发布不可变题目修订与审核提示，默认管理页仍使用原录题／审核流程。

旧院校列表的2025年估计值仍是演示数据，界面已标注，**不参与新推荐**。本轮未改造整个刷题/管理/认证系统，也不代表公网部署验收。

## 诊断、学情画像与自动推荐（2026-10-25）

代码已增加单选诊断、正式批次结束、服务器草稿、提示标记、幂等提交、不可变题目修订、撤回重算、规则画像及后台规则择校。**默认关闭**，不会自动操作当前数据库或重启服务。实际范围与验证见[本轮记录](docs/learning-loop-verification-2026-10-25.md)，业务契约统一见[搭建文档](考研Agent平台搭建文档.md)。

已有V12的库需先备份并核对迁移记录，在明确授权的维护窗口执行一次`kaoyan-B/src/main/resources/db/V13__learning_loop.sql`。脚本只新增表，不重跑V1；旧作答不回填提示或诊断依据。随后配置Java环境变量`KAOYAN_LEARNING_ENABLED=true`，一起更新Java、Python和前端。启用时缺少V13表会拒绝启动。关闭开关可保留已有数据回退；`L-`批次需重新启用功能后继续或结束，不能由旧提交逻辑绕过状态检查。

本机已于2026-10-25按用户后续授权完成`kaoyan_dev`的V13迁移：整库备份恢复及独立迁移预演通过，原17张表数据、字段和索引保持一致，新增10张表。根`.env`已保存`KAOYAN_LEARNING_ENABLED=true`；MySQL、Redis及三端已启动，访问[本机平台](http://127.0.0.1:5173/)。这只是本机当前状态，其他环境仍需自行核对迁移；本机不要重复执行V13。备份位置、验证及回退边界见[启用记录](docs/learning-loop-verification-2026-10-25.md#本机v13迁移与启用后续授权)。

首页及刷题页提供诊断入口，学习统计展示画像，院校页可保存自动推荐条件；自动推荐默认未开启，由本人保存开关。模型授权仍默认关闭，自动规则推荐不调用外部模型，沿用任务额度。当前日常题库只有数据结构，未补造四科题、审核估分蓝图或院校历史分数线；缺少资料时界面明确展示，不能把局部诊断当完整408预测。

新增隔离链路脚本（实际Java→Python、H2、Redis替身、合成四科夹具、模型关闭），需要先完成Java测试编译及测试类路径、前端生产构建：

```bash
# Java目录：bash mvnw -B -ntp test-compile dependency:build-classpath -Dmdep.includeScope=test -Dmdep.outputFile=target/test-classpath.txt
# 前端目录：npm run build
# 项目根目录，使用已安装依赖的Python；报告路径不得已存在
.cache/helloagents-venv/bin/python scripts/smoke-learning.py --output .cache/new-learning-loop-report.json
```

浏览器按既有方式配置`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`或安装Playwright Chromium。脚本只启动本次随机回环端口服务与独立浏览器上下文，结束后关闭本次进程；不连接日常MySQL、不读日常浏览器资料、不执行正式迁移。

## 独立功能测试环境（2027数据）

本机已准备10校15条官方来源专业、160道可练习自编题和12道审核样例，使用独立MySQL库及专用服务。[打开测试页面](http://127.0.0.1:15173)，账号、私密密码位置、复现命令、实际验证与限制见[独立测试环境说明](docs/feature-test-environment-2027.md)，[来源清单](docs/feature-test-sources-2027.md)保留招生核验依据。

这是独立测试环境，模型关闭。其数据不会自动同步；2026-10-23已按用户后续授权将公共院校、题库和资料另行合并到日常`kaoyan_dev`，正常5173页面也可使用，详见[日常库合并记录](docs/development-data-merge-2026-10-23.md)。预览使用 `python scripts/feature-test.py`，实际写入／启动须明确使用对应子命令和 `--apply`；完整入口见上述说明。独立环境脚本当前支持macOS/Linux，不改写日常`.env`或覆盖人工修改。

## 准备环境

### 服务器旧版公共资料合并预演（2026-11-03）

`scripts/prepare-server-data.py` 用于本次部署包的公共资料合并。默认只读预览；显式 `--rehearse` 使用服务器本机 MySQL root socket 备份现有库，在新建的独立库中恢复、执行缺失的 V13/V14/V15（2026-11-03起含V15；V15只有列或只有约束时拒绝）、验证编号映射、失败回滚及个人记录原有字段不变，最后仅清理本次独立库。**没有生产写入模式**，不会切换服务；备份及生成的 SQL 保存在指定的私密输出目录，不能作为自动上线命令执行。

```bash
python scripts/prepare-server-data.py --release-root /opt/kaoyan-releases/实际版本目录 --env-file /opt/kaoyan/.env --output /root/新的预览目录
# 确认使用服务器本机 MySQL root socket，在独立库中预演：
python scripts/prepare-server-data.py --release-root /opt/kaoyan-releases/实际版本目录 --env-file /opt/kaoyan/.env --output /root/新的预演目录 --rehearse
# 已有题目或资料不一致时，只读输出差异字段及有限的公开文本样本：
python scripts/prepare-server-data.py --release-root /opt/kaoyan-releases/实际版本目录 --env-file /opt/kaoyan/.env --output /root/新的诊断目录 --diagnose
```

需要已安装项目依赖的 Python、mysql、mysqldump；输出目录必须尚不存在。服务器采用其他管理认证时先核对连接，不修改认证设置。规则测试、本机独立 MySQL 验证及用户回传的服务器预演见[部署预演记录](docs/deployment-data-verification-2026-11-03.md)；服务器隔离预演通过，V13/V14和公共资料已提交，新版程序已切换、HTTPS公网入口已验证，登录业务待验收。

合并时，题目其余字段完全一致且仅 `permission_note` 不同时，保留服务器非空许可说明及原题编号，并在报告中单独计数；新增的当前版本快照同步保留该说明。已有版本快照及其他版本的原始说明不修改，答案、正文、解析、版本或其他来源字段不同仍拒绝覆盖。

2027专业备注比对仅兼容已观察到的“【2027官方来源核验摘要】／【官方招生事实】”及版本字段前“核验／核验日期”标签差异；其余学院、方向、考试条件、来源、版本及日期逐字比对。匹配后保留服务器原备注和编号，不更新备注，避免把原15条专业重复导入。规则pytest 15项及完整CLI隔离MySQL验证通过，服务器仍须使用更新工具重新预演并核对复用15条、新增782条。

`scripts/activate-server-release.py` 是上述已预演Ubuntu实例的受限正式更新工具，默认只读；显式 `--activate` 才开启维护、停项目服务、新备份及程序切换。首次更新已提交V13/V14和公共资料，但错误的Java探测导致程序回退；修复后用户使用 `--committed-activation` 成功切换新版且未重复导入。旧目录与凭证保留；诊断／学情与只读招生链接开关已启用，用户选择LLM暂时关闭。新IP HTTPS公网入口已检查；用户回传证书续期模拟及公开Embedding权重下载、512维本地编码通过。首次定时续期、题目索引和登录后业务验收仍待完成。真实范围及回退边界见[正式更新记录](docs/server-release-activation-2026-11-03.md)。

需要 Java 17、Python 3.13、Node.js 22（含 npm）；业务运行另需 MySQL 8 和 Redis。

从根目录执行（Windows PowerShell）：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r kaoyan-agent/requirements-dev.txt
.\.venv\Scripts\python.exe scripts/init-env.py
```

所有服务使用根目录 `.env`。脚本生成随机内部凭证与JWT签名密钥，不覆盖已有文件、不打印凭证。填写自己MySQL的 `DB_USER`、`DB_PASSWORD` 及 Redis 的 `REDIS_HOST`、`REDIS_PORT`、可选 `REDIS_PASSWORD`，不要沿用历史代码中的密码。Redis不可用时受保护接口会失败，不能通过关闭注销撤销来绕过。Python自动读取根 `.env`；Java由启动脚本显式加载。OSS可不配置，未配置时文件接口返回503，不阻止核心服务启动。

### 数据库

当前本机`kaoyan_dev`已具备V7—V13结构，无需重新建库或执行旧种子。真实数据入口为`scripts/import-real-data.py`，默认仅离线预览，`--inspect`只读核对；`--apply`涉及完整备份和明确演示数据清理，仅在授权范围执行。不要再执行V2—V6或旧演示seed把虚构内容补回日常库。真实数据及恢复步骤见[接入记录](docs/real-data-import-2026-10-24.md)，V13后续迁移见上述启用记录。

连续聊天版本启动前，须在已有V9基础上各执行一次`V10__chat_conversation.sql`、`V11__personal_document.sql`和`V12__assistant_privacy.sql`。这三份脚本新增会话、个人文档、隐私授权与助手操作表，保留旧任务；本次不自动操作日常数据库。新能力和兼容边界见[聊天契约](docs/conversations.md)。

仅在**全新空库**建立 `kaoyan` 并执行 `kaoyan-B/src/main/resources/db/V1__init.sql`，然后依次执行 `V7__practice_snapshot.sql`、`V8__task_soft_delete.sql` 和 `V9__question_source.sql`。V1含DROP语句，不能用于已有业务库。

已有数据库先核对已执行的迁移：V7为作答增加 `question_snapshot`，V8为任务增加 `deleted_at`；尚未执行的脚本各执行一次，已执行的不要重跑。**V8必须在启动本版Java前完成**，它保留现有任务、结果及额度依据，不清空数据。推荐删除后在历史中隐藏，仍计入每日及分钟额度。批次中任一有效作答缺少快照时，总结返回409，不创建任务或消耗任务额度；不使用最新题目补造历史。V2—V6属于旧演示种子，不是新推荐的数据源，V6的估计分数线不应导入正式库。迁移当前由开发者显式执行；尚未启用全仓库自动迁移。

本版题目录入依赖V9的六个来源字段；已执行V7/V8的数据库只需受控执行一次尚未应用的V9，完成后再启动新版Java。旧题来源保留NULL，管理页显示待补充，不改变已发布状态或历史快照。V9仅准备脚本，本次没有操作日常MySQL；迁移前检查、部分失败处理与代码回退见[录题与审核验证记录](docs/question-entry-review-verification.md)。不要执行含删除题目的V4种子脚本来扩充正式题库。

### 启动服务

先启动自己的MySQL和Redis，再运行以下服务。默认Java端口8080；若被占用，在后端终端设置 `$env:PORT="8081"`，前端终端设置 `$env:API_PROXY_TARGET="http://127.0.0.1:8081"`。

终端A：

```powershell
cd kaoyan-agent
..\.venv\Scripts\python.exe -m uvicorn main:create_app --factory --host 127.0.0.1 --port 8001
```

终端B，从根目录启动Java。确保 `JAVA_HOME` 指向JDK17：

```powershell
.\scripts\start-backend.ps1
```

终端C：

```powershell
cd kaoyan-frontend
npm ci
npm run dev
```

打开 [本地页面](http://localhost:5173)，注册并在个人中心填写2027年档案。院校库点击“条件推荐”，选择专业与学位类型；“智能问答”支持明确任务或自动识别。无MySQL时仍可独立验证Python接口和运行集成测试，不能据此声称实际MySQL联调已通过。

Linux/macOS使用 `python3.13 -m venv .venv` 和 `.venv/bin/python`。Java启动前在可信的根目录执行 `set -a; . ./.env; set +a`，随后进入 `kaoyan-B` 运行 `bash mvnw -B -ntp package` 和 `java -jar target/kaoyan-backend-1.0.0.jar`。运行Java测试时，设置 `PYTHON_EXECUTABLE` 为该虚拟环境Python的绝对路径。

## 扩充题库

管理员登录本地页面后，进入“题目录入与审核”→“批量导入”：

1. 下载JSON示例，或直接使用[四科8道自编题示例](kaoyan-frontend/src/assets/question-import-example.json)。这些是练习示例，不是历年真题。
2. 按示例的`{"questions":[...]}`格式整理题目，保留每题来源、定位和使用权限；真题另外填写整数年份和原题号。每批1—50题，界面文件上限2MiB，使用UTF-8编码。
3. 选择文件或粘贴JSON，点击“校验并预览”。展开题目核对答案与解析是否一致；发现错误先修改输入并重新校验。
4. 点击“确认整批送审”。全部合格才写入；失败保留输入，重复题会提示序号及已有ID。请求超时或中断时，先刷新待审核列表核对，避免盲目重试。
5. 关闭导入面板，在待审核列表逐题审核；只有通过且启用的题目才可被学生抽取。本地数据与线上服务器数据独立，导入本地不会自动更新线上。

复用已有V9来源字段，无新增迁移，无需运行旧种子脚本。本功能不自动采集真题，也不支持Excel／PDF识别；查重为科目、题干和四个选项的完整匹配，不是模糊查重或并发幂等。详细边界见搭建文档7.2.2。

## 启用中文向量检索

引用来源由共享文件[`config/reference-hosts.json`](config/reference-hosts.json)维护。默认Python直接读取，Java构建时将同一文件打包进JAR；新增来源先更新清单，再重建Java并加载两端新版配置。也可在两端设置`RAG_SOURCE_POLICY_FILE`为同一个绝对路径JSON文件；覆盖文件独立替换默认清单，不自动合并。配置缺失、格式错误或清单为空时拒绝启动，Python加载语料／导入索引前还会逐条检查来源。无需修改前端域名表；域名通过不代表资料内容或引用支持度已验收。详细规则见[RAG契约](docs/rag.md#引用来源策略)。

默认 `RAG_BACKEND=lexical`，不用下载权重即可检查规则、来源和页面。向量模式使用已实现的Qdrant＋FastEmbed，**不是把词项检索冒充Embedding**。

```powershell
cd kaoyan-agent
..\.venv\Scripts\python.exe ingest.py
```

该命令首次下载 `BAAI/bge-small-zh-v1.5` 中文模型，建立与语料及模型绑定的不可变集合；不调用付费LLM。然后把根 `.env` 中 `RAG_BACKEND` 改为 `qdrant`，重启Agent。

默认独立Qdrant数据库位于 `kaoyan-agent/.cache/rag/qdrant`，无需Docker。**本地模式仅单进程使用**：先停止Agent再导入。部署独立Qdrant服务时设置 `QDRANT_URL`、`QDRANT_API_KEY`；导入和服务需要相同资料、模型与索引标记目录。语料变更需先导入，再切换服务版本；缺少就绪标记不会返回部分索引。旧集合保留供回滚，不自动删除历史版本。

账号额度豁免：`QUOTA_EXEMPT_USERNAME` 默认 `robin`（精确匹配当前数据库用户名），该账号免每日／分钟任务额度及每日模型预算；设为空可关闭。由 Java 服务端决定，更新后需重启 Java 与 Python，保留超时及单请求调用上限。

## 可选只读资料MCP

知识检索默认`KNOWLEDGE_TOOL_TRANSPORT=local`，保持原路径。设置为`mcp_stdio`后，FastAPI生命周期管理一个固定本地Python子进程，知识及学情专家通过真实MCP协议调用原`retrieve_knowledge`；不新增端口、公开API或业务写入权限。`RAG_BACKEND`仍决定lexical／BM25／Qdrant／hybrid算法；题目索引和院校硬筛选保持原链路。

新机器按本文准备环境安装当前requirements即可。招生链接MCP与知识MCP共用当前依赖，已移除招生PDF解析依赖声明；已有环境保留额外包不影响链接功能，无需为此次改动卸载包。本机本次验证复用`.cache/mcp-pdf-venv`，新机器使用自行安装当前依赖的环境。需要自行启用知识MCP时，在加载相应配置的终端设置`KNOWLEDGE_TOOL_TRANSPORT=mcp_stdio`，从`kaoyan-agent`运行已安装依赖的Python与原`uvicorn main:create_app --factory`入口。Windows PowerShell使用`$env:KNOWLEDGE_TOOL_TRANSPORT="mcp_stdio"`。本轮没有修改真实.env或切换日常服务。

MCP仅接收query和可选subject，固定检索当前版本审核知识，最多5项；结构化结果超过64KiB或版本、来源、当前文档不一致均拒绝。启动／发现10秒、单次检索5秒、每轮最多3次，无自动重试或静默转本地，模型次数预算不变。超时／取消向远端发送对应通知；同步检索线程可能继续到本次只读工作结束，最多2线程，不宣称强制中止。程序退出清理会话及子进程。

2026-10-30起，知识和招生MCP由独立生命周期任务管理；单个工具启动失败不阻止Agent启动。`GET /health`保留原字段，新增`mcpTools.knowledge`和`mcpTools.admission`，每项为`{enabled,state,errorCode}`；本地知识模式／招生关闭显示DISABLED，实际可用显示READY，故障显示UNAVAILABLE。健康检查不执行工具；单次超时或无结果不等于断连。连接故障后拒绝后续调用，不自动重连、重试或切回本地；维护者检查故障码后按原入口重启Agent恢复。招生预算为请求内共享一次，日志提供内部调用编号、工具、耗时及固定错误分类，不记录查询正文。契约与实际检查见[可靠性记录](docs/mcp-reliability-verification-2026-10-30.md)。

向量模式只使用已有索引与权重，不自动建索引或下载（2026-11-02起服务进程强制只读本地权重，缺权重时检索不可用、混合模式回退BM25，权重须先由`ingest.py`准备）；本地知识Qdrant由子进程独占，不要与另一个进程使用同一个存储目录。隔离回归命令：

```bash
.cache/mcp-pdf-venv/bin/python -m pip check
.cache/mcp-pdf-venv/bin/python -m pytest -q kaoyan-agent/tests/test_mcp_knowledge.py
```

详细契约见[RAG说明](docs/rag.md#可选只读mcp检索2026-10-29)，真实验证与未运行项见[本轮记录](docs/mcp-knowledge-verification-2026-10-29.md)。需要停用时将传输配置切回`local`并在维护窗口重新加载对应服务；本文不自动重启已有进程。

## 启用AI解释

当前模型适配使用真实 `HelloAgentsLLM` 异步扩展，锁定 `hello-agents==0.2.8`、`openai==1.109.1`；依赖与必要传递约束见 `kaoyan-agent/requirements.txt`、`helloagents-constraints.txt`。原 LangChain 环境保留，迁移验证使用独立 `.cache/helloagents-venv`。真实模型默认关闭；AI笔记改写须授权，规则复习安排可以生成待确认笔记，手动笔记可用。运行环境切换见[本轮记录](docs/helloagents-multiagent-verification-2026-10-29.md#运行环境切换)，本次未重启日常服务。

聊天入口为 `/tasks`，登录／注册默认进入助手，原首页 `/` 与业务深链接保留。可以跳过诊断，直接聊天或提出“分析薄弱点，安排7天复习，并推荐院校”等复合请求；专家结果中的练习与笔记仍按现有确认流程执行。

在根 `.env` 填写供应商 `LLM_API_KEY`、HTTPS `LLM_BASE_URL`、模型名称，再设置 `LLM_ENABLED=true`。这将产生外部请求与可能的费用。代码关闭SDK重试。旧同步入口保持单次20秒、全流程42秒及最多2次尝试；复合聊天共享解析1次／10秒、专家阶段3次／28秒（2026-11-03由2次／20秒调整，剩余不足8秒不再发起模型请求）、可选汇总1次／4秒，Java保留48秒流程保护和浏览器55秒。 2026-11-01起使用统一PlanResolver与依赖调度：模型按专家优先级串行使用最多2次额度，只有无未完成依赖的纯规则步骤可并行；分项仍按计划顺序展示。单步`CONVERSATION_STEP_TIMEOUT`默认12秒（2026-11-02由8秒调整：DeepSeek学情步骤实测6.4—8.5秒；须小于专家阶段时限），超时保留独立步骤结果；阶段超时分别由`CONVERSATION_PARSE_TIMEOUT`、`CONVERSATION_EXPERT_TIMEOUT`、`CONVERSATION_SUMMARY_TIMEOUT`及`AGENT_TASK_TIMEOUT`配置，默认10/28/4/42秒，阶段之和须不超过总超时且总超时小于48秒。结果可含分项状态与部分完成提示，旧历史兼容；详见[专家编排审核修复记录](docs/expert-audit-verification-2026-10-30.md)。

上下文已增加离线输入预算与确定性裁剪，原始授权快照不改写；整篇笔记及必要错题内容超限时零模型请求降级。输出按能力分配，拒绝供应商长度终止的结果，不自动续写或重试。预算默认值与配置关系统一见[搭建文档](考研Agent平台搭建文档.md#统一规划与执行预算契约2026-11-01)，示例变量在`.env.example`；本地token估计不等于供应商实际用量。旧同步CHAT只兼容单任务，复合／学情／笔记请求提示转到`/tasks`。本轮实现、验证及未运行范围见[P0验证记录](docs/planning-budget-scheduling-verification-2026-11-01.md)。

使用 **DeepSeek 官方 V4.1 Flash** 时，在本机编辑根 `.env` 的以下已有项，不要覆盖数据库、JWT或内部凭证：

```dotenv
LLM_ENABLED=true
LLM_API_KEY=在本机填入DeepSeek官方APIKey
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL_MAIN=deepseek-flash
LLM_MODEL_ROUTER=deepseek-flash
```

填写后只测Python链路可从项目根目录运行`cd kaoyan-agent`，再运行`../.cache/helloagents-venv/bin/python -m uvicorn main:create_app --factory --host 127.0.0.1 --port 8001`（此路径为本轮独立验证环境；其他机器使用自行安装requirements的虚拟环境）。`GET /health`的`modelEnabled=true`仅代表配置开启，不代表供应商调用成功。整站`/tasks`测试还需要新版Java、Redis和已应用V10/V11/V12的数据库；不可通过重跑V1准备已有业务库。2026-10-22已完成两轮Python链路的DeepSeek真实请求，范围和整站待办见[接入验证记录](docs/deepseek-verification-2026-10-22.md)。


### 可选招生官网链接 MCP

当前登记范围已从10校扩展到院校库全部**121校**（新增111校，包含北京大学、清华大学），逐校入口和核对限制见[官网登记清单](docs/admission-source-catalog-2026-11-01.md)。其中浙江大学、武汉理工大学、云南大学提供已核对的学校HTTPS主页导航，需进入研究生招生栏目；南京师范大学采用官方迁站提示的新入口。只补充链接，不代表121校年度招生数据已审核。2026-11-01按用户后续明确授权重启本机三端并加载新版登记表，北大、清华、矿大北京的内部规则查询及前端121校清单检查通过；随后按用户关闭指令，已正常停止三端、项目MCP、MySQL及Redis，相关端口均已释放，需重新启动后访问。旧回答不自动重新生成；登录后的日常页面操作尚未实际验收。

范围扩展的构建、121校协议检查及北京大学隔离三端验证见[验证记录](docs/admission-scope-verification-2026-11-01.md)。隔离链路可复现为`.cache/mcp-pdf-venv/bin/python scripts/smoke-chat.py --admission --admission-school pku --output .cache/new-pku-chain.json`，沿用本文测试类路径与浏览器准备条件；不传`--admission-school`时继续检查南京审计大学。

`ADMISSION_MCP_ENABLED=false`为默认值；设置为`true`后，按原FastAPI入口重新加载Python服务，自动管理独立招生stdio子进程。该开关与`KNOWLEDGE_TOOL_TRANSPORT`独立，不增加监听端口或数据库迁移。该子进程只读取`config/admission-sources.json`并公开`get_admission_links({schoolCode})`，返回`{schoolCode,schoolName,registeredYear,entryUrls}`；不执行DNS、HTTP、HTML／PDF解析、模型调用或审核语料比对。`registeredYear`是维护者登记的配置年份，不代表网址当前内容年份或最新招生年度。

可输入“查官网南京审计大学”“南京审计大学查官网”“帮我查询北京航空航天大学招生信息”“给我南京审计大学招生网址”或“核对南京审计大学招生信息”。只需提供一个已登记院校；缺少院校、同时出现多所院校或院校未登记时先澄清，不追问年份、学院、方向或专业代码。输入“你可以查询哪些学校官网”只列出登记院校、登记年份和入口网址，不调用模型或工具。招生MCP关闭、启动失败、超时或结果校验失败时返回`UNSUPPORTED`并明确提示，不静默改用本地链接。

助手历史、任务历史及Word／PDF／Markdown导出只展示登记院校、登记年份、完整有序的登记网址及“请自行确认招生年份、专业及报考条件”。旧`admissionCheck`记录保留在数据库JSON中但不迁移；展示和导出按登记院校投影安全网址，隐藏旧核验正文、状态、差异、摘录、哈希、核验时间、基线和限制，复合结果中的院校候选仍保留。历史记录中的旧招生结论不会再次进入模型上下文。

```bash
# 默认离线检查登记清单；不联网、不读模型/业务配置
.cache/mcp-pdf-venv/bin/python scripts/check-admission.py
# 显式启动真实stdio MCP逐个查询登记链接；不联网、不使用模型或业务数据库
.cache/mcp-pdf-venv/bin/python scripts/check-admission.py --mcp --output .cache/new-admission-links.json
# 仅检查一个登记院校
.cache/mcp-pdf-venv/bin/python scripts/check-admission.py --mcp --school nau
```

`--output`必须指向尚不存在的文件。旧爬虫参数`--live`和`--transport local`会被参数解析拒绝，不存在自动抓取回退路径。启动／发现10秒、单次本地查询5秒，每轮最多一次。`GET /health`的`mcpTools.admission`继续提供`{enabled,state,errorCode}`；连接故障后不自动重连，维护者检查后按原入口重启Agent恢复。2026-11-01按用户后续授权重启本机三端并通过本次Agent进程环境启用招生MCP，实际检查见[验证记录](docs/admission-links-verification-2026-11-01.md#日常三端重启后续授权2026-11-01)。根`.env`未修改，此启用方式仅对当前Agent进程有效，后续重新启动时需再次设置`ADMISSION_MCP_ENABLED=true`。

## 验证

2026-10-25补充：已修复启用学情后`L-`批次编号38字符超过既有MySQL字段36字符的问题；新普通练习／诊断统一生成34字符编号，不需修改日常数据库。故障原因、真实临时MySQL验证及本机加载见[批次编号修复](docs/assistant-practice-navigation-verification-2026-10-25.md#批次编号超长修复2026-10-25后续)。

独立MySQL建卷回归：完成上述依赖、Java测试编译及测试类路径准备后，运行`.cache/helloagents-venv/bin/python scripts/smoke-managed-mysql.py --output .cache/new-managed-mysql-report.json`。脚本使用本机MySQL服务端／客户端程序（可用`--mysqld`指定服务端路径），初始化全新临时数据目录、随机回环端口及独立Java／Python进程；仅在该空实例执行V1及V7—V13，使用Redis／供应商／向量替身，结束后清理本次进程和临时数据，不连接日常数据库。输出报告必须使用不存在的新路径。

Windows从根目录执行：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q kaoyan-agent/tests
$env:PYTHON_EXECUTABLE = (Resolve-Path .\.venv\Scripts\python.exe).Path
Push-Location kaoyan-B
.\mvnw.cmd -B -ntp verify
Pop-Location
cd kaoyan-frontend
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
```

Java测试在独立H2库启动真实Python子进程，不读日常MySQL，也不调用模型；子进程结束后清理。浏览器测试使用已有生产构建的Vite preview、隔离上下文和模拟API；须先执行`npm run build`，避免开发态依赖优化重载干扰迟到请求测试。验证页面、历史显示、来源、文本安全和390宽度；不等于整站真实手机验收。

检索/引用质量评测默认离线，不调用模型；`--model` 才读取根`.env`并产生真实供应商请求与费用。使用已安装当前HelloAgents依赖的Python环境执行（本轮隔离环境为`.cache/helloagents-venv`）：

```bash
.cache/helloagents-venv/bin/python scripts/eval-quality.py --output .cache/quality-report.json
.cache/helloagents-venv/bin/python scripts/eval-quality.py --backend bm25 --output .cache/quality-bm25.json
.cache/helloagents-venv/bin/python scripts/eval-quality.py --model --only qa-stack,qa-tcp --output .cache/quality-model.json
```

报告路径已存在时拒绝覆盖；本轮结果与限制见[质量评测记录](docs/quality-eval-2026-10-24.md)。

浏览器也可通过 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 指定本机Chrome或Edge；不读取日常浏览器资料。CI已按三个新目录执行Python、Java真实链路、前端构建与浏览器测试。实际验证结果见 [本轮验证记录](docs/validation-rag.md)。

## 隔离HTTP与真实后端浏览器检查

保留并更新上游的链路脚本，使用随机端口、临时H2、Redis／模型替身，不读取日常业务数据。浏览器检查使用生产构建产物及Vite preview，避免开发依赖首次优化刷新打断登录；`/api`代理仍指向本次临时Java端口。先在kaoyan-frontend执行 `npm ci`、`npm run build`，再在kaoyan-B生成测试类路径：

```powershell
.\mvnw.cmd -B -ntp test-compile dependency:build-classpath '-Dmdep.includeScope=test' '-Dmdep.outputFile=target/test-classpath.txt'
```

再从根目录运行（报告路径必须尚不存在）：

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH = '本机Chrome或Edge可执行文件的绝对路径'
.\.venv\Scripts\python.exe -X utf8 scripts/smoke-current.py --output .cache/new-http-report.json --browser-check --node node
```

无本机浏览器时先安装前端Playwright Chromium；省略浏览器环境变量即可使用其默认浏览器。Linux/macOS使用 `.venv/bin/python`。脚本验证实际HTTP调用、分页、注销、跨账号、超时前落库、真实进程重启和来源结果展示；不代表真实Redis／模型供应商验收。缺少构建产物时会在启动临时服务前报错。失败诊断保存在独立的 `.cache/smoke-debug-*`，包含服务日志及可用的浏览器截图、异常类别和接口路径／状态，不记录请求头、正文或令牌。任务配额按UTC日重置，单Java实例通过短事务保存，不在调用Python时持有数据库事务。

## 题目管理隔离页面回归

在前端完成生产构建、后端完成 `test-compile dependency:build-classpath -Dmdep.includeScope=test -Dmdep.outputFile=target/test-classpath.txt` 后，从根目录执行：

```bash
python scripts/smoke-question-admin.py --output .cache/new-question-admin-browser.json
```

使用已安装项目依赖的Python（macOS／Linux可使用`.venv/bin/python`），浏览器按前述Playwright安装方式准备，或通过`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`指定本机Chrome。
脚本使用随机回环端口、专用内存H2、Redis替身和独立浏览器上下文，自动创建测试账号；测试夹具拒绝写入其他数据库。检查1280与390宽度下的录题、过期编辑、审核、停用／恢复、学生权限和历史快照，完成后关闭临时进程。报告路径已存在时拒绝覆盖；不读取日常数据库、不调用模型，也不代表真实MySQL或手机实机验收。


## 本地题目语义检索

复用现有依赖，无新增数据库迁移。新Java、Python及前端需一起加载；本次不自动重启已有服务。题目索引独立于知识资料的RAG_BACKEND，默认使用本地持久Qdrant；Python仅接收Java提供的已发布题目副本。

从项目根目录准备本地权重（首次下载公开模型文件，不调用付费模型，不读取业务库）：

```bash
.cache/helloagents-venv/bin/python scripts/prepare-question-model.py
```

上例使用本项目现有验证环境；独立安装时用README准备环境得到的`.venv/bin/python`，Windows为`.venv\Scripts\python.exe`。EMBEDDING_MODEL沿用`BAAI/bge-small-zh-v1.5`；QUESTION_MODEL_CACHE默认`kaoyan-agent/.cache/embedding`（2026-11-02起RAG向量索引与知识MCP子进程也使用该缓存，不再用系统临时目录）；QUESTION_INDEX默认`kaoyan-agent/.cache/questions`，QUESTION_MIN_SCORE默认0.75。权重、索引与缓存均不提交。模型来源、许可及实际效果见[验证记录](docs/question-semantic-search-verification-2026-10-24.md)。

示例：“将我的错题本中涉及二叉树的题目加入收藏”“在收藏夹中找关于二叉树的题目”“从全题库创建5道关于二叉树的题目练习”。首次查询或题库变更后可能显示索引准备中；准备完成后可点“重试此问题”。未就绪不生成操作，已就绪零匹配另行提示。所有主题操作先预览确认，缺题时明确实际数量。

独立真实本地模型验证：

```bash
.cache/helloagents-venv/bin/python scripts/verify-question-semantic.py --output .cache/question-model-new-report.json
```

隔离页面验证（独立H2、随机端口、临时浏览器目录、真实Qdrant，向量使用测试替身）：

```bash
.cache/helloagents-venv/bin/python scripts/smoke-chat.py --questions --output .cache/question-browser-new-report.json
```

页面脚本沿用既有Node/Chrome配置，需先完成Java verify和前端build。旧题目索引不自动删除；经授权停用Agent后可运行`scripts/maintain-question-index.py --keep <完整版本>`查看清单，确认范围后再加`--apply`。这不操作业务数据库或知识资料索引。
