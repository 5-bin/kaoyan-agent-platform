# 院校信息检索MCP候选与匿名烟测（2026-10-30）

> 2026-11-01状态：招生自动抓取、解析与核验已被仅提供登记网址的方案替代。当前实现见[招生官网网址契约](../考研Agent平台搭建文档.md#招生官网网址契约2026-11-01替代自动核验)。以下原始记录保留，仅证明当时的环境与验证范围。


本轮从[Smithery目录](https://smithery.ai/servers)筛选搜索与页面读取服务，再核对厂商官方文档，并使用本项目`.cache/mcp-pdf-venv`的MCP 1.12.4客户端进行实际Streamable HTTP调用。仅发送公开官网URL及院校／年份／专业查询；不读取根.env、不使用API Key、不登录／付费、不修改系统DNS、项目配置或运行服务。

## 结论

**当前环境优先试接Exa官方MCP，Tavily作为提供API Key后再评估的候选。** Exa本次匿名搜索和读取均取得目标官网内容；Firecrawl、Jina、Tavily虽然可连接，但匿名业务请求均未取得结果。因此不能仅依据目录评分、连接成功或工具的isError=false判定可用。

[Smithery官方公告](https://smithery.ai/future)说明：2026-10-31停止MCP Proxy、连接管理、Smithery API／CLI／SDK及run.tools／server.smithery.ai地址，保留公共目录。新接入应直接使用供应商官方端点，不依赖Smithery中转地址或安装器。

## 候选与实际结果

| 候选 | 官方能力依据 | 本轮匿名实测 |
| --- | --- | --- |
| [Exa：Smithery条目](https://smithery.ai/servers/exa) | [官方文档](https://exa.ai/docs/get-started/exa-mcp)：搜索、已知URL读取；匿名限流试用；官方端点`https://mcp.exa.ai/mcp` | 搜索约2592毫秒，命中南京审计大学2027目录及原登记URL；读取约2582毫秒，返回含081200、计算机学院、全日制及101／201／301／408的内容 |
| [Tavily：Smithery条目](https://smithery.ai/servers/Tavily) | [官方MCP文档](https://docs.tavily.com/documentation/mcp)、[匿名模式](https://docs.tavily.com/documentation/keyless)：搜索／抽取，匿名需`X-Tavily-Access-Mode: keyless` | 搜索5730毫秒、抽取6011毫秒，均返回`monthly_cap_reached_bonus_eligible`；isError=false，但属于业务额度失败。未注册、答问换额度或付款 |
| [Jina：Smithery条目](https://smithery.ai/servers/jina) | [官方仓库](https://github.com/jina-ai/MCP)：read_url读取网页／PDF；搜索及结构化PDF抽取需要Key | 连接／发现成功；read_url约11726毫秒，返回匿名IP信誉限制HTTP401，未取得页面 |
| Firecrawl | [官方仓库](https://github.com/firecrawl/firecrawl-mcp-server)、[官方MCP文档](https://docs.firecrawl.dev/mcp-server)：搜索、抓取、解析，文档提供有限匿名入口 | 连接／发现成功；firecrawl_scrape约11382毫秒，返回该请求匿名访问不可用，要求API Key。Smithery旧条目本轮未呈现有效详情，因此以官方仓库为能力依据 |

以上时间为各工具本次单次调用耗时，不含连接初始化，不是延迟承诺或覆盖率评估。Exa已知URL读取的初始化约1002毫秒、含关闭总计4149毫秒；Firecrawl／Jina的初始化本次均约6秒。不能默认所有官网或PDF均能落入项目12秒预算。

测试目标为南京审计大学2027年081200、计算机学院。Exa搜索命中同域的`c4394a161925`及原登记的`c4397a161925`两个目录URL；正文同时含国际学院的同代码项目，后续仍必须按学院／年份／学位／方式区分，不能只匹配专业代码。

读取烟测的必要摘录与测量保存在本机缓存`.cache/admission-mcp-candidates-20261030-141541.json`；Tavily在`.cache/admission-mcp-tavily-20261030-141628.json`。Exa搜索另外在本次工具输出中记录，未保存完整页面。没有把供应商提取文本当成原始HTML或宣称已计算原页面hash。

## 对项目替换的建议（尚未实施）

当前[招生客户端](../kaoyan-agent/core/admission_client.py)只接受一个特定工具及本项目AdmissionResult Schema；因此不能仅将子进程命令／URL换成第三方MCP。当前取证器也要求存在同年审核基线，主要完成“核验已登记条目”，缺少面向信息发现的通用搜索能力。

建议分两项能力处理：

1. 用Exa搜索定位已批准院校官网，再读取选定页面，返回来源链接、标题、必要摘录及取得时间。无本地基线时仍可展示“实时未审核资料”，不冒充与平台资料一致。
2. 有同年、同学院／专业组合的基线时，才执行现有字段比对；保留Java校验、正式持久化及未审核标记。官方来源不足或被截断时明确降级。

外层保留HelloAgents院校专家及受约束领域工具，在适配层连接Exa远程MCP。只开放必要搜索／读取工具，限制结果数量、来源域名、正文长度及调用次数；核对远程SDK当前Schema，不能复制旧示例工具名。Markdown／纯文本需要独立证据提取与复核，不能继续直接交给HTML表格解析器，也不能伪造PDF页码／bbox。若引入模型结构化提取，必须共用既有模型预算和外发规则，不增加隐藏模型调用。

云端服务负责访问院校官网，本机连接供应商；这可以减少本机对院校域名Fake IP解析的影响，但供应商连通性、缓存新鲜度、重定向、地域可读性及结果真实性仍需独立验收。现有直连取证器继续保留公网校验，不为接入云端而放行198.18.*。

实施前需更新搭建文档及三端结果契约，明确“实时查找”和“基线核验”的语义、12秒内搜索与读取的预算及失败行为，再增加隔离测试和真实域名案例。建议验收至少覆盖静态HTML、文字PDF、动态目录、相同代码不同学院、跨年结果及配额失败；目前仅验证一个官网HTML案例，尚未验收其他九校、PDF、长期稳定性或接入后的整站效果。
