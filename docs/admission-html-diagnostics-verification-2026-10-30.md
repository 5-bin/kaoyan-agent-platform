# 招生HTML解析与分阶段诊断验证（2026-10-30）

> 2026-11-01状态：招生自动抓取、解析与核验已被仅提供登记网址的方案替代。当前实现见[招生官网网址契约](../考研Agent平台搭建文档.md#招生官网网址契约2026-11-01替代自动核验)。以下原始记录保留，仅证明当时的环境与验证范围。

2026-11-02提交前核对：下文历史解析器、诊断模块及夹具已随旧方案移除，路径仅作历史定位，不是当前可运行入口。


本轮修复全宽学位分节使后续行丢失、专业组合单元格无法匹配的问题；将DNS拒绝、HTTP响应、HTML结构和字段对齐分别诊断。不修改系统DNS、Shadowrocket、代理、真实.env、来源清单、正式资料或业务数据，不启动／重启日常服务。

## 实现与兼容

- HTML解析器（历史路径 `kaoyan-agent/tools/admission_html.py`）保留表号、原始行号、表头、分节及跨行列。明确的全宽学位分节不再使表格失效；未知合并／无效span拒绝，遇明确新表头或独立学位分节后重建上下文。嵌套布局表与内部数据表各自隔离，不将内部表文字拼成外部招生行。
- 取证与字段校验（历史路径 `kaoyan-agent/tools/admission.py`）识别明确组合列中的专业代码、专业名、学院及完整方向列表，学习方式取各方向显式值；唯一初试科目列支持两位序号且仍要求四个不同的三位代码。缺方式、混合方式、任选科目、方向独立科目、组合列跨行或结构未知时不推算。原简单表头／rowspan及PDF取证路径继续兼容。
- 摘录保存实际分节文字、列标题及原始行内容；跨行时附带从HTML属性得到的列信息。HTML定位示例为“表1／原始行4／专业081200／分节行1”。MCP客户端从保存摘录重新提取并检查相同招生组合，不依赖仅在子进程存在的解析状态。
- 公共AdmissionResult、MCP工具名／Schema、任务终态、Java和前端接口不变。五字段SAME仍为PARTIAL，保留资格／方向待核对；明确科目变化返回DIFFERENCES。实时证据继续UNREVIEWED，不更新正式推荐、RAG或releaseId。

诊断使用独立类型与请求内上下文（历史路径 `kaoyan-agent/core/admission_diagnostics.py`），默认关闭，每次核验最多80个白名单事件。阶段为DNS／HTTP／HTML／FIELDS／CHECK；只包含callId、公开域名和IP／公网判定、HTTP状态、最多160字符标题、结构计数、原始位置及字段名，不包含完整页面、请求正文、凭证或异常原文。HTML的matchedRows为初筛候选数，学院只在备注出现的行可能进入候选，但仍须通过字段复核。

诊断开关仅由检查脚本构建的可信AdmissionConfig传入stdio子进程，不开放给查询参数。MCP默认继续丢弃stderr；显式诊断时在私有临时目录收集stderr，脚本仅将严格校验的admissionDiagnostic事件写入检查报告，再清理临时文件。local诊断在直接取证进程采集；报告标明transport，不能冒充MCP验收。生产公开结果不包含diagnostics。

## 实际环境与验证

使用本项目`.cache/mcp-pdf-venv`：Python 3.13.15、hello-agents 0.2.8、openai 1.109.1、mcp 1.12.4、pydantic 2.10.3、httpx 0.28.1、pytest 9.1.1。未安装新依赖或修改其他项目环境。

回归夹具nau-sections.html（历史路径 `kaoyan-agent/tests/fixtures/admission-html/nau-sections.html`）按公开版式人工构造，含colspan=4分节、重复表头、专业／学院／五个方向拼接、括号学习方式及四个带序号科目；同代码国际学院条目使用不同科目作隔离对照。它不是官网冻结副本，不是审核资料。

| 验证 | 实际结果 |
| --- | --- |
| 新增解析／诊断、原招生HTML及PDF回归 | 103项通过，21.32秒 |
| Python全量回归 | 516项通过，75.38秒；命令如下 |
| 全量后补充表头／正文分隔符防歧义复核 | 新增解析／诊断测试模块30项通过，3.68秒 |
| 真实stdio MCP＋合成结构页面 | PARTIAL，5项SAME；原始表／行／分节定位保留，客户端独立复核通过 |
| 真实stdio MCP＋合成Fake IP答案 | UNAVAILABLE，无证据／比较；报告仅有DNS NON_PUBLIC，未进入HTTP／HTML |
| 检查脚本`--school nau --diagnostics`，未加`--live` | live=false，单校配置，results为空；不启动MCP或联网 |
| `git diff --check` | 通过 |

完整回归命令（项目根目录）：

```bash
.cache/mcp-pdf-venv/bin/python -m pytest -q kaoyan-agent/tests
```

新增用例覆盖：分节切换与跨表隔离、嵌套表、未知colspan／非法span、rowspan边界、相同代码不同学院、年份错误、冲突科目、方向缺方式／混合方式、方向科目独立、跨行组合、冲突学习方式列、Fake IP及IPv4／IPv6混合公私地址、DNS异常／取消、零HTTP断言、全公网IPv4／IPv6连接固定与Host／SNI、HTTP403、诊断限额／隔离／非法字段拒绝，以及真实MCP中诊断开关与脚本采集。既有回归还覆盖预算、超时、取消、PDF回收及HelloAgents工具入口。测试有两项既有弃用警告：Starlette对AnyIO接口的使用及Pydantic旧配置方式；未升级依赖。

## DNS与后续真实复测

规划阶段于2026-10-30从本项目`.cache/mcp-pdf-venv`只读检查过11个登记域名，当时全部解析为198.18.*、is_global=false。这只说明该时点环境存在网络前置拒绝，不能解释已取得HTML后的解析失败，也不说明官网失效。本轮按用户后续决定不修改DNS规则，未重新请求真实官网。

保留精确域名、HTTPS、公网及混合答案拒绝、逐跳验证、IP固定连接、原Host／TLS SNI、trust_env=false、12秒及六次请求预算、无自动重试。DNS失败或非公网答案会明确提示并在诊断中标记DNS阶段，不尝试HTTP，不放行198.18.0.0/15或写死官网IP。

用户准备好真实公网解析环境后，从同一虚拟环境执行（输出路径必须尚不存在）：

```bash
.cache/mcp-pdf-venv/bin/python scripts/check-admission.py --live --school nau --diagnostics --output .cache/new-admission-nau-diagnostics.json
```

默认transport=mcp，在实际招生子进程内采集。先确认每次DNS答案全部isGlobal=true，再检查HTTP状态、HTML计数及FIELDS结果；官网仍为同一招生组合和科目时，预期五项SAME、整体PARTIAL，若原文变化则以实际证据为准。少字段、访问限制或结构改变仍应降级，不能把状态强制改成成功。

真实官网HTML／PDF内容烟测、十校逐校准确性、真实MySQL／Redis、付费模型、Java verify、前端构建／浏览器及部署均**未运行**；本轮未修改Java／前端代码，不将合成链路结果扩大为真实官网或三端业务验收。
