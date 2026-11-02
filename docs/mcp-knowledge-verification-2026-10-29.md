# 只读资料 MCP 第一阶段：实现与验证

日期：2026-10-29，Asia/Shanghai。本轮按确认方案完成真实 stdio MCP 链路，默认保留本地检索；不修改真实 `.env`，不切换日常服务，不操作日常业务库，不调用付费模型，没有提交、推送或部署。

## 实现与职责

```text
Java 授权请求
  → FastAPI / Workflows
  → 原生 HelloAgents McpKnowledgeSearchTool
  → 共享异步 MCP ClientSession
  → 当前 Python 解释器启动的固定 stdio 子进程
  → 原 KnowledgeSearchTool / Retriever / Corpus
  → 结构化证据
  → 客户端再次校验并还原 RetrievalHit
  → 原知识／学情专家、引用校验与 Java 保存流程
```

- [客户端及原生工具](../kaoyan-agent/core/mcp_client.py)：适配器继承现有 `ValidatedTool`，通过现有 HelloAgents 注册表装配，专家继续调用原 `ainvoke` 接口。一个应用进程共享一个会话，不按请求启动子进程。
- [固定服务入口](../kaoyan-agent/mcp_server.py)：仅注册 `retrieve_knowledge`，复用真实 HelloAgents 检索工具与原算法。工具不接受用户编号、URL、文件路径或执行代码；没有业务库、模型调用及写入能力。
- [双端契约](../kaoyan-agent/core/mcp_contract.py)：输入沿用 `SearchParameters`，输出是 `{releaseId,retrievalBackend,documents}`；每份 Document 保留完整来源、定位、版本和审核字段，最多5项。原公开 API、任务／终态、结果与 SSE 字段不变，详细契约维护于[RAG说明](rag.md#可选只读mcp检索2026-10-29)。
- `KNOWLEDGE_TOOL_TRANSPORT=local|mcp_stdio` 默认 `local`；仅装配路径变化，`RAG_BACKEND`仍控制 lexical、BM25、Qdrant 或 hybrid。题目语义索引及院校硬筛选不走 MCP。

MCP 启动／发现10秒，单次检索5秒；每轮API生成最多3次检索，预算按请求共享，SSE生成另设本轮计数。没有自动重试或静默切回本地。原专家阶段及模型调用预算保持现状。

客户端拒绝工具清单／Schema变化、错误或无结构化响应、超过64KiB的结构化结果、重复文档、错误版本／后端、非当前知识文档，以及正文／来源／其他字段篡改。科目过滤响应也需符合本轮请求。异常沿用原同步任务失败或学情局部降级，不公开原始SDK异常。

## 依赖核验

独立创建 `.cache/mcp-phase1-venv`，使用本项目 requirements 安装，没有复制或修改原虚拟环境。实际环境为 macOS arm64、Python 3.13.15；Java 使用 JDK25，编译目标17。

| 依赖 | 本轮实际版本 |
| --- | --- |
| HelloAgents | 0.2.8，保持原锁定 |
| OpenAI SDK | 1.109.1，保持原锁定 |
| Pydantic／pydantic-settings | 2.10.3／2.7.0，保持原锁定 |
| FastAPI／Starlette／HTTPX | 0.115.6／0.41.3／0.28.1 |
| 官方 MCP SDK | 1.12.4 |
| sse-starlette | 3.0.3 |
| fastmcp 外部包／CLI extras | 未安装 |

新增依赖及传递约束已精确锁定在原 requirements／constraints 中。`pip check` 通过；原 `.cache/helloagents-venv` 仍没有安装 MCP。原环境不会因工作树增加代码自动具备新依赖，重新启动新版代码前需安装对应 requirements。

选择 MCP 1.12.4 是为了维持当前 Pydantic 基线，仅验收固定本地 stdio。没有沿用书中宽松 extras，也没有修改安装包源码；以后升级 SDK 或增加 HTTP 传输需重新核验。

## 取消、线程和关闭

锁定 SDK 的 `send_request` 在取消／超时时清理本地等待，但不会自动发送远端取消通知。项目通过保持原签名的 `CancellingClientSession` 扩展，在对应工具请求取消时发送 `notifications/cancelled`，发送本身有0.25秒保护，不关闭其他请求共享的会话。请求编号依赖已核对的1.12.4预留顺序，升级时必须重验。

真实 stdio 回归确认远端异步处理器收到取消、其他并发请求继续成功、后续请求可复用连接。另用生产服务及人工延迟的同步检索验证最多2个工作线程：等待方取消后，已经运行的同步读可能继续到结束，但不产生无限补充线程、不再发布取消结果。

FastAPI lifespan 在同一任务中进入和退出 SDK 会话及 stdio 上下文。退出关闭 stdin、等待子进程结束；必要时 SDK 进行进程树终止与升级处理。测试捕获实际子进程对象，确认正常关闭、错误工具清单及启动超时之后均已退出。沙箱内部分强制进程组操作会由 SDK 回退到单进程终止；本服务不启动下游子进程，实际捕获的服务进程均已回收，未据此宣称任意进程树都已验收。

子进程只传固定检索配置和必要运行变量，不继承业务／模型凭证，不实例化读取根 `.env` 的 Settings。stdout保持协议消息，原始子进程／SDK诊断不直接转发；项目日志仅记固定类别、异常类名及耗时，不记查询或资料正文。

## 实际检查结果

| 检查 | 实际结果及范围 |
| --- | --- |
| Python全量 | **363通过**，23.67秒；包括原有328项和新增35项MCP回归 |
| MCP专项 | **35通过**，20.29秒；真实独立stdio子进程、原生工具执行、参数及证据拒绝、账号请求与预算隔离、超时、取消、断进程、事件循环响应及关闭 |
| Java全量 `verify` | **175项，0失败／错误／跳过**；Maven耗时51.158秒，默认本地工具路径 |
| 显式启用MCP的Java→Python | `AgentChainTest` 13项、`ConversationIntegrationTest` 19项，共**32通过**，Maven耗时39.257秒；真实随机回环端口、内部HTTP与stdio子进程 |
| 依赖 | 新隔离环境 `pip check` 通过；既有环境未安装MCP |
| 证据一致性 | lexical、BM25及hybrid缺索引回退与原工具的完整文档、顺序、来源相同；覆盖无结果和过滤后回退 |
| Qdrant所有权 | 临时真实Qdrant、测试替身向量；服务运行时第二连接被拒绝，子进程退出后可重新打开，未下载权重 |
| 文档／配置／差异 | 175处本地链接、锚点、38个Markdown表格、Python语法、CI路径、新公共函数类型／文档字符串及空白差异检查通过 |

32项MCP Java检查是175项全量中的相关测试重新执行，不将二者相加；35项专项也已包含在363项全量中。Java使用临时H2、Redis替身；聊天模型使用受控SDK传输，测试中的 `LLM_ENABLED=true` 不表示访问真实供应商。

首次专项28项中的3项失败：取消通知少传SDK要求的method字段，以及对比夹具的本地hybrid路径创建了测试索引目录。已补齐通知字段，对比改用相同的只读索引前提，保持检索与来源断言。后续全量暴露两个新增夹具问题：原语料可省略metadata、网络资料ID前缀实际为cn；均按真实夹具修正，没有放宽正式校验。最终结果见上表。

保留原Starlette／框架Pydantic弃用提示；系统受限环境可能报告ONNX遥测标识无法落盘，不涉及业务数据。原生向量模型质量及实际知识覆盖并未因这些检查得到证明。

本机日志为忽略目录中的 `.cache/mcp-phase1-install.log`、`mcp-phase1-targeted.log`、`mcp-phase1-python.log`、`mcp-phase1-java.log`、`mcp-phase1-java-mcp.log`。任务前相关源码快照及公开文件摘要在 `.cache/mcp-phase1-originals/`；没有复制真实 `.env`、数据库、索引或旧虚拟环境。

公开文件摘要复核确认，本轮仅改动13个相关既有文件并新增6个任务文件；原有Java、前端、CI及其他并行改动保留。静态结果保存在 `.cache/mcp-phase1-static.json`。

## 复现与运行边界

已有本轮隔离环境可从项目根目录运行：

```bash
.cache/mcp-phase1-venv/bin/python -m pip check
.cache/mcp-phase1-venv/bin/python -m pytest -q kaoyan-agent/tests
```

Java默认路径完整检查：

```bash
export PYTHON_EXECUTABLE="$PWD/.cache/mcp-phase1-venv/bin/python"
cd kaoyan-B
bash mvnw -B -ntp verify
```

另在Java目录显式选择MCP，运行已有隔离链路测试：

```bash
KNOWLEDGE_TOOL_TRANSPORT=mcp_stdio bash mvnw -B -ntp -Dtest=AgentChainTest,ConversationIntegrationTest verify
```

上述命令已经在本轮执行。创建其他机器的新环境遵循README安装requirements，不复制本机环境。MCP服务由FastAPI固定启动，不需要另起监听端口；本轮没有将这些配置写入真实 `.env` 或切换日常进程。

**未运行**：真实供应商及token／费用、真实Embedding权重与远程Qdrant、本机日常MySQL／Redis验收、前端构建与浏览器、Windows、Linux线上CI、公网及部署。无前端或Java业务源码变更、无数据库迁移。向量检查只证明协议与存储生命周期，不证明真实模型召回质量。
