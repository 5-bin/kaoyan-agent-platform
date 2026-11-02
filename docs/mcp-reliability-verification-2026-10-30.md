# MCP调用可靠性：实现与验证

> 2026-11-01状态：本文的招生自动取证／核验部分已被替代；知识MCP及通用生命周期约束仍按当前契约保留。当前实现见[招生官网网址契约](../考研Agent平台搭建文档.md#招生官网网址契约2026-11-01替代自动核验)。以下原始记录保留，仅证明当时的环境与验证范围。


日期：2026-10-30，Asia/Shanghai。按确认方案完善既有知识及招生MCP，不新增工具权限或付费模型调用。主契约见[搭建文档](../考研Agent平台搭建文档.md#阅读导航)、[RAG](rag.md#mcp调用可靠性2026-10-30)及[会话](conversations.md#mcp调用可靠性2026-10-30)；运行入口见[README](../README.md#可选只读资料mcp)。

## 实现与兼容

- [公共运行适配](../kaoyan-agent/core/mcp_runtime.py)负责独立连接所有者任务、只读健康状态、固定错误、单次调用及关闭。知识／招生客户端保留各自参数、来源与领域结果校验，继续通过真实HelloAgents原生工具调用真实stdio；不复制框架或修改安装包。
- 两个工具独立启动与停用；初始化或发现失败先回收进程，再报告UNAVAILABLE，Agent及另一工具继续运行。运行中接收循环结束会清除会话并拒绝后续调用，没有后台重连或静默本地回退。原直接`connect()`调用仍报告启动异常；FastAPI使用显式故障隔离模式。
- 连接由单一所有者任务进入、退出SDK上下文；关闭先拒绝新调用，再取消内部RPC等待，最多0.5秒做一次协议ping往返，保证先前取消通知送达后再关闭管道并回收进程。ping不执行工具／模型，不占业务预算，没有自动重试。单请求取消不关闭其他请求的共享会话；同步知识工作线程继续遵守原有最多2个线程的边界。
- [请求预算](../kaoyan-agent/core/runtime.py)新增共享`admission_budget`，替换会被子任务分别复制的布尔变量。同步、规划和SSE分别设置CallBudget(1)，知识仍CallBudget(3)；每次已提交的失败／超时／取消占用次数，非法参数及不可用连接不占次数，新请求重新获得预算。
- `GET /health`新增`mcpTools`，原status、releaseId、retrievalBackend、modelEnabled、admissionMcpEnabled、provider不变。knowledge/admission各返回enabled、state、errorCode；状态为DISABLED／STARTING／READY／UNAVAILABLE／CLOSED，errorCode为连接故障的固定分类或null。健康检查只读内存，不调用工具；业务UNAVAILABLE／NEEDS_INPUT、超时或结果拒绝不会被误判为连接中断。
- 固定错误码为START_FAILED、CATALOG_CHANGED、SCHEMA_CHANGED、CONNECTION_CLOSED、TIMEOUT、CALL_LIMIT、TOOL_FAILED、RESULT_INVALID、INTERNAL_ERROR。招生专家映射为既有limitations提示，知识沿用现有失败／局部降级；任务类型、终态、结果字段、SSE及Java持久化结构不变，无迁移。
- 日志仅记录内部随机调用编号、固定工具名、结果分类、耗时、预算使用／上限；不记录查询、个人内容或凭证。保留MCP 1.12.4的send_request、接收循环及输出校验签名。该版本接收循环使用root logger输出协议验证详情，因此只针对该依赖文件的日志安装幂等脱敏过滤器；其他日志不受影响，升级SDK须重验。

## 实际检查

使用已有本项目`.cache/mcp-pdf-venv`，没有复制或修改环境／依赖。macOS ARM64、Python3.13.15；实际安装版本为HelloAgents0.2.8、MCP1.12.4、Pydantic2.10.3、OpenAI1.109.1、pdfplumber0.11.10、psutil7.2.2。Java使用JDK25.0.4.1、目标17，前端使用Node22.23.3及已有npm依赖。

| 检查 | 结果及范围 |
| --- | --- |
| Python全量pytest | **466项通过**，75.82秒；新增30项可靠性检查，包含local对照及真实PDF子进程关闭；保留2条已有弃用警告 |
| Java `verify` | 181项通过，失败／错误／跳过均0，53.933秒；显式KNOWLEDGE_TOOL_TRANSPORT=mcp_stdio，含真实Java→Python链路 |
| 关闭竞态修复后的Java链路复测 | AgentChainTest13项、ConversationIntegrationTest20项，共33项通过，Maven42.367秒；这些是181项中的相关项重新执行，不相加 |
| 前端生产构建 | 通过，Vite5.23秒；保留已有大资源块提示 |
| 真实三端隔离浏览器 | 13项通过；Vue→Java→FastAPI→stdio→实际PDF解析，含桌面1280／390宽度、页码链接、刷新、跨账号404、Java重启恢复 |
| 依赖与静态 | pip check通过；文档链接／锚点、Python语法、JSON／CI路径及空白差异检查通过 |
| 官网真实读取 | 默认MCP路径10次工具调用正常，连接READY；10校业务结果均UNAVAILABLE，因DNS解析到非公网地址被拒绝连接，未取得真实内容 |

新增真实stdio检查覆盖：两类工具的目录／Schema错误、启动超时、缺少可执行文件、启动中取消、空闲EOF、调用中退出、关闭时在途请求、结果伪造、工具异常、非法协议通知脱敏；同时启用两类工具且一类故障时另一类和HTTP继续服务。招生并行3次只提交1次，另两次明确CALL_LIMIT；跨账号请求、同步／规划／SSE均重置并隔离预算。SDK私有扩展签名与当前安装版本逐项核对。

原PDF测试之前依靠布尔ContextVar复制给子任务，使共享连接上的第二个调用隐含拥有独立额度；本轮将测试明确分为不同请求预算，保留实际取消、超时、进程PID及临时目录清理断言。首次新回归发现工具名称变化被归为Schema变化，已修正为目录变化并验证对应提示。原专项首轮106通过／2失败，修正请求夹具后专项55通过；后续补充检查以最终全量为准，不将历史批次重复累计。

新增关闭PDF子进程的回归随后暴露真实竞态：SDK的send_notification只等待写队列接收，紧接着关闭连接可能中断实际写入；服务端没有及时收到取消，超过SDK退出等待后被终止，留下请求临时目录。该次全量465通过／1失败，未将其写成成功。修复为上述有界协议往返后，关闭专项3项通过（4.26秒），确认解析PID消失和临时目录清理；失败测试遗留的本次专用临时目录在确认PID已退出后单独清理，没有清理用户资料。

浏览器首次受沙箱限制无法启动Chrome；申请执行放行后，使用独立临时资料目录通过13项检查。两次运行都仅启动／清理本次随机端口进程，未重启日常服务。官网页面／PDF为明确自编夹具，模型供应商和Redis使用替身，保存使用临时H2；这些结果不等于真实招生内容、MySQL或供应商效果验收。

关闭竞态修复后重跑完整Python及相关Java／浏览器链路，最终浏览器报告为`.cache/mcp-reliability-chain-complete-20261030.json`；Python／Java／前端日志为`.cache/mcp-reliability-python-complete-20261030.log`、`mcp-reliability-java-20261030.log`及`mcp-reliability-frontend-20261030.log`，Java复测日志为`.cache/mcp-reliability-java-chain-20261030.log`。官网报告为`.cache/mcp-reliability-live-20261030.json`，报告明确transport=mcp及当轮mcpStatus=READY。协议成功与官网未取证分别记录，未将DNS限制描述为学校官网故障。交付时再次检查5173／8080／8001均无监听进程，日常服务保持关闭。

## 复现与剩余范围

```bash
# 根目录；不会修改.env、业务库或启动日常服务
.cache/mcp-pdf-venv/bin/python -m pytest -q kaoyan-agent/tests
.cache/mcp-pdf-venv/bin/python -m pytest -q kaoyan-agent/tests/test_mcp_runtime.py
.cache/mcp-pdf-venv/bin/python scripts/check-project.py
.cache/mcp-pdf-venv/bin/python scripts/check-admission.py
# 以下显式联网，报告路径必须未存在
.cache/mcp-pdf-venv/bin/python scripts/check-admission.py --live --output .cache/new-mcp-admission-live.json
.cache/mcp-pdf-venv/bin/python scripts/check-admission.py --live --transport local --output .cache/new-local-admission-live.json
```

Java目录使用`PYTHON_EXECUTABLE="$PWD/../.cache/mcp-pdf-venv/bin/python" KNOWLEDGE_TOOL_TRANSPORT=mcp_stdio bash mvnw -B verify`；前端目录`npm run build`。浏览器检查先按README生成Java测试类路径，然后根目录执行：

```bash
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  KNOWLEDGE_TOOL_TRANSPORT=mcp_stdio .cache/mcp-pdf-venv/bin/python scripts/smoke-chat.py \
  --admission-pdf --output .cache/new-mcp-reliability-chain.json
```

未修改真实`.env`、数据库、迁移、默认开关或日常运行状态；未提交、推送或部署。**未运行**：真实MySQL／Redis验收、真实模型及token／费用、Windows／Linux、真实手机、远端CI及公网部署。十校真实网页／PDF内容准确性仍未验收；原本地检索线程及PDF观测内存阈值的限制见原验证记录，不因本轮连接可靠性改造而扩大承诺。
