# DeepSeek 专家编排建议审核与修复（2026-10-30）

对象为本项目当前工作树及用户提供的12项建议。保留原有未提交修改，没有创建分支、提交、推送、操作日常数据库、切换日常服务或调用真实供应商。契约先于代码更新；正式定义见[搭建文档增量契约](../考研Agent平台搭建文档.md#专家编排审核修复契约2026-10-30)，此处仅记录审核、实现及验证证据。

## 审核结论与实际修改

| 建议 | 核对结论与落地 |
| --- | --- |
| 1. PRACTICE为空实现 | 成立。PracticeAgent改为直接继承StructuredAgent，独立负责受控练习及其他已有操作的规则反馈；与学情共用本地结果构造函数。单操作继续直接返回，不额外读取知识或调用模型。 |
| 2. 多处解析漂移 | 成立。新增intents.py，集中IntentResolver、ConditionExtractor及原学习／文档解析；原learning.py导出兼容函数。知识＋专业推荐、错题分析＋专业推荐保留双重意图；练习＋笔记对象不明先澄清，不生成操作。 |
| 3. 合并字段丢失及Java覆盖 | 成立。公共结果有类型校验，合并使用专家字段归属表，保留操作摘要、计数、证据、followUp及支持度；合并同编号证据／引用内容冲突拒绝，超过20条引用拒绝。Java正式证据及actions优先，不覆盖复合回答全文。 |
| 4. NOTE失败语义不一致 | 成立。预期供应商、超时及模型输出校验失败返回UNSUPPORTED/fallback，不生成占位建议；复合请求保留其他结果。 |
| 5. 宽泛捕获掩盖错误 | 成立。专家只降级明确的SDK、模型输出、预算及工具可用性异常；普通RuntimeError、TypeError等继续传播，由入口保存FAILED。协调器的兜底捕获只记录类别并重新抛出。旧供应商替身改抛明确的ModelUnavailable，冻结输出及调用参数断言未放宽。 |
| 6. 预算分配不确定 | 成立。按计划顺序执行专家，实际模型尝试合计最多2次；无preparedPlan时先完成最多1次解析，再按已用次数初始化2／4次总预算，不修改已有计数器limit。 |
| 7. 超时分散 | 成立，但不是单纯替换数字。集中Settings配置及启动校验，解析和汇总同时限制适配层单次超时，保留专家阶段及总超时、Java48秒保护。 |
| 8. NOTE动态属性传参 | 成立。改为显式StepContext，仅传入声明了STUDY_PLAN依赖的类型化快照；上游未完成或缺计划时不生成笔记。 |
| 9. 部分完成与汇总 | 成立。增加可选sections/partial，未增加任务或领域终态；notice与未完成状态分开。仅全部完成、均为获授权AI结果且无notice时尝试汇总，规则私人摘要不二次外发。 |
| 10. 日志及回归缺口 | 成立。增加专家及会话的结果、模式、耗时、尝试数及异常类别日志；不新增正文或个人标识。新增路由、NOTE、程序错误、确定性预算、依赖、合并及三端回归。 |
| 11. 框架适配深度 | 部分描述不准确：模型层已有真实AsyncHelloAgentsLLM继承。保留现有适配，不引入新的模型旁路、持久记忆、上下文截断或付费摘要；架构文档明确GSSC沿用授权投影和JSON规范化的范围。 |
| 12. 低风险小项 | 已落实明确context错误、统一执行边界的元数据及结果校验、instruction长度、模块logger及条件括号。保留原生框架字符串执行与字典服务入口所需的JSON转换。 |

复现更正：`分析错题并推荐专业`原实现实际只保留LEARNING_ANALYSIS、丢失择校；原建议写成只保留择校，方向相反。另两条示例分别落到DOCUMENT_CREATE和CHAT，均已核对。最初复现为直接调用，不能算完整HTTP验收。

Java实际使用TaskServiceImpl.validateResponse及ConversationService专项校验，没有建议所称的通用validateResult方法；本轮沿用真实入口并增加分项校验，没有放宽计划、专家或权限白名单。

## 回归中发现并修复的兼容问题

- 首轮Python定向回归中，旧替身以任意RuntimeError表示供应商不可用，与新策略冲突；改为ModelUnavailable并保留冻结结果断言，另外用TypeError验证单笔记及复合笔记必须产生错误事件，不能返回成功结果。
- 首轮Java验证3项失败。两项是把收藏操作错误升级为复合专家导致额外知识检索；已恢复仅PRACTICE_CREATE参与既有复合计划，其他单操作由独立PracticeAgent按原路径处理。
- 另一项暴露真实恢复问题：知识完成而练习索引BUILDING时，总outcome为COMPLETED，旧重试门槛返回409。已同步Java与Vue，仅在部分完成、PRACTICE未完成、指定检索故障状态且无actions时开放原重试入口；继续校验最后一条问题、当前账号授权与配额。Java集成回归实际经过索引就绪、重试、确认及重复确认。
- 首次Chrome因沙箱限制在启动阶段失败，未运行页面断言；获准在沙箱外使用临时浏览器目录复测后通过，没有接管日常浏览器资料。

## 环境、命令与证据

本机macOS、Python3.13.15、Node22.23.3、JDK25.0.4.1，Java编译目标17。本轮没有用JDK17运行验收。Python使用已有`.cache/mcp-pdf-venv`，框架及SDK保持锁定版本；Java用本项目Maven缓存，未升级依赖。业务验证只使用临时H2、独立题目索引、Redis替身及受控供应商传输，不连接日常MySQL。

| 验证 | 实际结果及本机证据 |
| --- | --- |
| 修改前定向基线 | multiagent、conversation、tutor_conversation及practice_intent，共58项通过。 |
| Python全量 | 486项通过，71.42秒；`.cache/expert-audit-python-verified-20261030.log`，两条既有Starlette／Pydantic弃用提示。 |
| 修改后定向 | 最后复核专家审核、冻结行为、多专家、隐私及练习意图5组共153项通过，1.83秒；含两条引用冲突／超限拒绝回归及兼容学习入口的操作委托。 |
| Java全量verify | 183项通过，0失败／错误／跳过，55.020秒；`.cache/expert-audit-java-final-20261030.log`及target/surefire-reports。 |
| 前端生产构建 | 通过；`.cache/expert-audit-frontend-final-20261030.log`，保留既有较大chunk提示。 |
| 相关Playwright | multiagent及assistant-practice-navigation桌面1280／手机宽度390，共28项通过，15.0秒；`.cache/expert-audit-browser-final-20261030.log`。包括新旧历史、分项恢复、部分完成的重试按钮及已有操作禁止重试。 |
| 真实三端浏览器及重启 | 13项通过；`.cache/expert-audit-chat-20261030.json`。使用实际Vue／Java／Python／HelloAgents，涵盖两种宽度的复合分项及刷新恢复、连续追问、笔记创建修改确认、取消重试、历史与Java进程重启恢复；未拦截浏览器业务API。 |
| 静态与差异 | 本次Agent及新适配代码的Ruff通过，目标Python3.13；脚本node语法检查及git diff --check通过。 |

复现命令（从项目根目录运行，已有报告路径不可覆盖）：

```bash
.cache/mcp-pdf-venv/bin/python -m pytest -q kaoyan-agent/tests
# Java：进入kaoyan-B后运行，PYTHON_EXECUTABLE指向上述Python的绝对路径
bash mvnw -B -ntp verify -Dmaven.repo.local=../.cache/maven/repository
# 前端：进入kaoyan-frontend后运行
npm run build
npm run test:e2e -- multiagent.spec.ts assistant-practice-navigation.spec.ts
# 根目录，使用新报告文件名；浏览器可按README指定本机Chrome
.cache/mcp-pdf-venv/bin/python scripts/smoke-chat.py --output .cache/new-expert-audit-chat.json
```

本次扩大静态扫描时也看到未修改的MCP模块有已有未使用导入及默认Python目标版本提示；没有为本任务清理无关文件。通过结论限于明确列出的本次改动范围。

## 未运行与限制

真实供应商、真实token／费用测量、日常MySQL／Redis、真实手机、JDK17运行、公网及部署检查均**未运行**。所有模型均为替身，不代表领域内容或学习效果验收。未执行迁移、导入、资料更新、模型费用操作或日常进程重启。

顺序调度保持专家阶段20秒；较早专家占满时间时，后续分项会明确未完成。专家阶段最多两次生成，因此三个以上需要AI的专家通常不触发汇总；每日模型预算仍是单Python进程内计数。旧历史缺新字段继续按旧格式展示，无需回填。
