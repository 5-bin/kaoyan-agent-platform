# 统一规划、上下文预算与专家调度验证

日期：2026-11-01。范围：当前工作树的Python规划与模型输入、专家调度、Java计划交叉校验及相应文档。保留任务开始前已有修改；未创建分支、提交、推送或迁移，未删除业务历史、题目、笔记或索引，未操作日常服务。

## 实现与接口

详细契约集中在[搭建文档](../考研Agent平台搭建文档.md#统一规划与执行预算契约2026-11-01)，不在本文件重复维护预算表。

- [PlanResolver](../kaoyan-agent/agents/resolver.py)统一新旧入口。移除Workflows的独立模型路由及协调器的`_resolve_legacy`分支；同步门面只投影可表达的单任务，复合请求提示使用主助手。公开任务类型、终态、结果保存及SSE不变，历史读取适配保留。
- 能力词表由[intents.py](../kaoyan-agent/intents.py)共用。否定按分句处理，操作指令单独提取，保留独立正向请求；复合收藏／取消收藏也由PRACTICE承担，避免只处理另一个意图；复习天数默认7，支持1—30，中文数字可识别，越界或多天数冲突先澄清。功能咨询和示例不能授权操作。准备计划、模型结果及执行前均检查动作、依赖、读取／操作及必要快照；Java在业务读取前独立交叉校验。
- [上下文组件](../kaoyan-agent/core/context.py)继续继承HelloAgents ContextBuilder并执行其build/GSSC生命周期，返回`PreparedModelInput`。相关性选择用于保留更相关的摘录和统计分组，大统计列表批量选择以避免逐行重新计算完整上下文，确定性压缩在模型输入副本上进行；系统规则、问题、元数据、资格条件及判分依据不截断。个人文档整篇修改超限拒绝，不生成部分替换建议。
- [离线计量](../kaoyan-agent/core/tokens.py)只从本地缓存读取并校验cl100k_base词表，不通过tiktoken下载入口。无词表时使用标为`utf8_piece_upper_bound`的保守估算；有词表时标为`cl100k_base_estimate`，两者均不是供应商真实用量。输入计量含系统提示、输出Schema及JSON包装。
- 输出按能力设置上限，普通和流式响应都拒绝`finish_reason=length`。预算预检、模型关闭或客户端构造失败不消耗模型尝试；即将提交供应商请求时原子检查每日、请求和阶段额度。实际失败或取消仍计数，无自动续写／重试。
- [调度器](../kaoyan-agent/core/scheduling.py)按就绪依赖与模型优先级执行，每步有deadline；只有明确禁用模型的纯规则步骤可并行，检索／MCP仍串行。模型额度未使用时留给下一候选，耗尽后计划按规则完成，笔记明确未生成。最终sections按计划顺序排列，取消回收所有子任务，程序错误保持整体失败。
- 复合请求修改笔记但未选择文档时先澄清；明确创建新的复习笔记时不把内容追加到界面已选中的旧文档。文档始终由Java在用户确认后保存。

## 实际验证

环境：macOS、Python 3.13.15、HelloAgents 0.2.8、OpenAI SDK 1.109.1、Pydantic 2.10.3、tiktoken 0.14.0、JDK 25.0.4.1（工程目标Java 17）、Node 22.23.3。复用本项目`.cache/mcp-pdf-venv`，未安装或升级依赖；模型全部使用受控替身／SDK MockTransport，不读取日常业务数据。

| 检查 | 实际结果 | 范围 |
| --- | --- | --- |
| Python全量pytest | 614项通过，2条依赖弃用警告，55.29秒 | 包含真实HelloAgents接口、同步、plan、SSE、历史、工具、预算、超时和取消的现有及新增回归；不是供应商验收 |
| 新增P0测试 | 54个参数化测试案例，包含于上述614项 | 19种常见／否定／复合说法，越界与缺文档澄清、非法计划、长输入、可见引用、截断拒绝、调度优先级及请求隔离 |
| Java verify | BUILD SUCCESS；211项中209项执行通过、2项跳过，53.034秒 | H2及受控Python子进程链路，独立验证计划、持久化、跨账号、失败及重启恢复 |
| 前端生产构建 | npm run build通过 | Vue/TypeScript和Vite生产构建；保留大于500kB的资源块提示，不等于浏览器验收 |
| 差异检查 | git diff --check通过 | 保留既有工作树修改，未提交 |

Java跳过项均为原有ExportIntegrationTest的真实Redis检查：`actualRedisLuaAtomicallyEvictsAndRejectsExpiredEntries`和`ownershipVersionsAllFormatsAndClearedSources`；本轮未启用该外部环境。

新增测试位于[test_planning_budget_scheduler.py](../kaoyan-agent/tests/test_planning_budget_scheduler.py)，Java交叉校验见[ConversationPlanValidationTest](../kaoyan-B/src/test/java/com/kaoyan/service/ConversationPlanValidationTest.java)。历史JSON基线文件未重生成；对应测试只显式适配已批准的路由输出额度、JSON空白和新增来源元数据，其他逻辑输入与公开结果仍核对旧基线。旧操作测试补上了匹配的当前用户指令，不能再靠preparedPlan单独授权写操作。

首轮回归发现并修复：重新校验时默认条件覆盖未设置补丁；文档优先级误遮蔽复合请求的练习操作校验；否定分句的空片段及Java正则转义。不是仅调整断言来跳过这些失败。

## 复现入口

从项目根目录执行Python；本机Maven Wrapper没有执行位，使用bash运行，并显式指定已安装项目依赖的Python供Java隔离链路使用。首次Java检查未指定Python时因系统无`python`命令失败，补齐环境后全量通过；未更改Wrapper权限或真实配置。

```bash
.cache/mcp-pdf-venv/bin/python -m pytest -q kaoyan-agent/tests
```

在`kaoyan-B`目录执行：

```bash
PYTHON_EXECUTABLE="$PWD/../.cache/mcp-pdf-venv/bin/python" bash ./mvnw -B verify
```

在`kaoyan-frontend`目录执行：

```bash
npm run build
```

本轮最终完整日志位于本机`/tmp/kaoyan-p0-pytest-20261101-final.log`与`/tmp/kaoyan-p0-maven-20261101-final.log`，临时日志不作为跨机器运行依赖。

预算锁顺序统一后，额外运行每日配额拒绝、并发预算、请求隔离及零请求降级5项测试，通过；包含在主测试覆盖范围内，不与614项相加。

## 限制与未运行项

- 真实模型、供应商实际token用量／费用、30天计划的真实生成耗时及内容效果：未运行。默认输出上限不保证一次模型生成成功；截断、错误或超时使用规则结果，笔记不生成占位建议。
- cl100k_base仅是本地估计；未知供应商tokenizer可能不同，无缓存的保守上界会提前拒绝部分实际上可容纳的长输入。额度可在受控配置中调整，仍须满足总窗口及预留校验；不会自动下载词表或付费总结。
- 引用支持仍是现有词项检查，不能证明语义蕴含。知识和择校既有支持校验使用实际可见内容；学情混合私人事实与知识引用，正文发生节选时执行保守检查，不能将编号合法宣称为全面领域正确。
- 日常MySQL、真实Redis导出、日常服务重启、浏览器人工操作、真实手机及公网部署：未运行。新版代码尚未加载到日常服务；本轮只启动测试自身管理的隔离子进程。
- 取消会关闭本地SDK等待与流；不声称供应商已经停止远端计算或停止计费。Python每日预算仍是单进程内存计数，重启后重置，不是账单硬上限。
