# 招生官网取证 MCP：实现与验证

> 2026-11-01状态：招生自动抓取、解析与核验已被仅提供登记网址的方案替代。当前实现见[招生官网网址契约](../考研Agent平台搭建文档.md#招生官网网址契约2026-11-01替代自动核验)。以下原始记录保留，仅证明当时的环境与验证范围。


> 同日后续已扩展文字型PDF；下文保留HTML阶段的历史验证与限制。当前PDF能力、依赖环境和验证见[PDF扩展记录](mcp-admission-pdf-verification-2026-10-29.md)。

日期：2026-10-29。范围为当前项目工作树；未提交、推送或部署，未修改真实 `.env`，未切换日常服务，未连接日常 MySQL／Redis，未调用真实模型供应商。

## 已实现的行为

学生或管理员在本人助手明确输入“查官网南京审计大学2027年081200招生目录”，触发内部 `ADMISSION_CHECK`。协调器通过 SCHOOL 专家的原生 HelloAgents 执行入口，调用注册的 `AdmissionCheckTool`，经真实 stdio MCP 执行 `check_admission_updates`。普通择校不联网，工具不接受 URL、HTTP 方法、表单、用户编号或聊天正文。

新开关 `ADMISSION_MCP_ENABLED` 默认关闭，与知识检索 `KNOWLEDGE_TOOL_TRANSPORT` 独立；依赖沿用 `hello-agents==0.2.8`、`openai==1.109.1`、`mcp==1.12.4`、`pydantic==2.10.3`，没有新增依赖、业务表或迁移。FastAPI lifespan 管理独立招生子进程；子进程只接收语料与来源策略文件路径，不加载根 `.env`，不创建模型客户端、Qdrant 索引或业务数据库连接。

来源清单为 [`config/admission-sources.json`](../config/admission-sources.json)，基于现有10校事实来源和公开查询证据登记：南京审计大学、中国科学院大学、中国传媒大学、北京航空航天大学、四川大学、华南师范大学、燕山大学、郑州航空工业管理学院、浙江科技大学、安徽师范大学。登记2027来源、学院、精确域名、入口及必要版权说明；北航公开只读POST参数、川大及华南师大GET详情来自现有夹具，不从用户或模型生成。来源清单同时打包给 Java 和前端，变更后需要配套构建／加载。

**登记10校不等于当前运行语料必然有10校。** 基线只取当前 `RAG_DATA` 实际加载的审核副本；默认小语料仅覆盖部分院校。查到其他年份、多个学院或没有同年基线时，先澄清／返回 `NEEDS_INPUT`，不切换年份或采用页面上的“采集待核实”记录。

## 比对、保存与失败边界

- 每轮一校一年一专业，明确学院条件必须匹配；方向条件缺少结构化基线时人工核对。完整年份、学院、专业、学位和学习方式对齐后，才比较可定位字段。
- 支持静态HTML表格、明确表头和简单 rowspan；不猜测复杂 colspan、缺失跨行条件或方向对应关系。混合学位、学习方式、多个方向、相互矛盾科目及缺字段不能判为一致；不同招生组合不能冒充改考。
- 抽取专业名、学院、学位、学习方式及明确的四门初试科目。不用模型抽事实、猜字段、解释网站脚本或生成差异。与推荐复合请求保留审核副本的规则候选，不增加模型解释请求。
- 实时结果放在 `admissionCheck`：`query/baselineReleaseId/checkedAt/status/entryUrls/limitations/evidence/comparisons`。状态为 `CONSISTENT/DIFFERENCES/PARTIAL/UNAVAILABLE/NEEDS_INPUT`，属于该结果内部状态，不是新增任务终态。
- 本版因资格和方向尚未形成完整基线，正常取证通常为 `PARTIAL` 或 `DIFFERENCES`；不以“部分字段一致”宣称全部招生条件一致。
- 每项证据有独立 `A1—A6` 编号、来源链接／标题／位置、必要摘录、获取时间、明确元数据可取得的公告日期、正文UTF-8内容SHA256、版权说明和固定 `UNREVIEWED`。未知公告日期为null，不从URL猜日期。
- 每项比较保存字段、旧值、新值、`SAME/CHANGED`、原资料ID及本次证据ID，绑定同年 `baselineReleaseId`。它们不进入原 `references`，不伪造语料发布版本，也不进入正式推荐或索引。
- Java校验查询与计划一致、来源映射、结构／长度、证据编号及差异关系，再保存到原任务／会话JSON；Python客户端还核对当前冻结基线的成员、旧值及原文观察。归属、清除和保留期沿用已有助手规则，管理员也只能查看本人会话，不新增跨账号管理列表。
- PDF、图片、压缩响应、验证码、403、未知编码、无法识别表格或动态站点均明确限制并给出登记入口。官网失败不声称没有招生或已经停招；正式审核发布继续原离线流程。

执行限制：启动／发现10秒、工具总限时12秒、每轮最多一次、最多6次HTTP尝试（包含重定向）、全服务最多2个并发官网请求。原专家20秒及Java48秒保护保留，无自动重试。每跳重新检查精确域名、HTTPS、无凭证／非标准端口限制与公网DNS；请求固定到已校验IP，同时保留原Host及TLS SNI。固定POST查询不自动跟随重定向。拒绝压缩响应，按identity传输读取最多2MiB正文，结构化结果最多64KiB，超限拒绝。

取消通知针对对应MCP请求，取消异步HTTP等待并丢弃迟到结果，其他共享会话请求继续。系统DNS解析的底层线程不承诺被强制终止；取消后不继续发起HTTP。stdout仅用于协议，日志不输出原始个人上下文或凭证。

## 实际验证

环境：本项目 `.cache/mcp-phase1-venv`，Python 3.13；Java使用当前本机JDK与项目Java17编译目标；前端使用已有Node／npm依赖。本次没有新建或复制其他项目环境。

| 检查 | 实际结果与范围 |
| --- | --- |
| `pip check` | 通过，无依赖冲突；有本机pip缓存目录不可写提示，不影响检查 |
| Python全量pytest | 406项通过，27.41秒，含新增43项招生检查；框架已有2条弃用警告 |
| Java `bash mvnw -B verify` | 179项通过，53.691秒；`mvnw`文件无执行位，按README使用bash执行，无更改权限或脚本 |
| 前端 `npm run build` | 通过，最终构建3.54秒；保留已有大资源块提示 |
| 招生页面Playwright | 桌面1280和390宽度共4项通过，模拟接口覆盖差异、不可读、刷新恢复和无横向溢出 |
| 实际三端／MCP隔离链路 | 11项通过：Vue→Java→FastAPI→真实stdio→合成官网页面；覆盖证据卡片、原文链接、刷新、跨账号404、Java重启后证据一致及中断任务恢复 |
| 文档／JSON／语法检查 | `scripts/check-project.py`及`git diff --check`通过 |

新增Python检查覆盖10校配置和合成表格、静态表头／rowspan、科目变化、年份错误、学院／方向／学习方式错位、同页冲突、未知参数／工具／Schema、超大结果、伪造来源／版本／基线／引用、公私混合DNS、私网跳转、PDF／403／压缩／超大页面、固定POST、请求预算、全局并发与HTTP取消、真实stdio调用、远端取消通知、超时后共享连接继续使用、模型零调用和普通推荐不联网。

十校表格夹具是**明确生成的合成页面**，用于验证解析和约束，不是十校官网抓取或教师复核结果。链路模型供应商和Redis使用替身，业务保存使用隔离H2；招生页面替身运行在独立真实MCP子进程中，不绕过协议。没有产生真实供应商用量或费用，不能以此评价真实招生事实或模型效果。

首轮浏览器检查因沙箱不能启动Chrome失败；获准后使用独立临时Chrome资料目录运行。一次移动端测试因测试脚本抢先点击隐藏的历史按钮超时，修正为等待已恢复的结果区域后4项通过；没有为测试修改产品历史行为。最终真实链路另使用随机端口、临时H2和独立Chrome，结束后清理本次服务，不操作已有进程。

本机报告：`.cache/admission-chain-final-20261029.json`；真实链路截图：`.cache/chat-browser-1793282307621424000/admission-1280.png`与`admission-390.png`。本机测试日志保留在 `/private/tmp/kaoyan-admission-*.log`，这些是本轮本机证据，不是运行依赖。

## 官网联网烟测与未验收范围

执行了只读 `scripts/check-admission.py --live`，并在首次失败后使用获准网络权限复测。10校均返回 `UNAVAILABLE`；当前环境把官网域名解析为 `198.18.*`（包含相应IPv6形式）的非公网地址，安全策略在连接前拒绝，未绕过校验。最终明确原因的报告为 `.cache/admission-live-final-20261029.json`；这不是10校网站本身均失效的结论。

因此，**10校真实页面抓取、逐校真实内容解析、真实变化准确性均未验收**。需要在正常公网DNS环境重新运行烟测，并按原文独立核对每项差异；当前网络环境无法生成可信的十校真实页面冻结夹具。实际PDF／OCR、需执行JS的查询和复杂合并表格未实现，返回人工核对；公网部署、真实MySQL／Redis回归、真实模型、真实手机与远端CI均**未运行**。

## 复现与启用

不启用任何日常服务即可检查配置和运行Python测试：

```bash
# 项目根目录
.cache/mcp-phase1-venv/bin/python scripts/check-admission.py
.cache/mcp-phase1-venv/bin/python -m pytest -q kaoyan-agent/tests/test_admission.py
```

三端隔离链路前先在Java目录执行：

```bash
PYTHON_EXECUTABLE=/绝对路径/本项目/.cache/mcp-phase1-venv/bin/python bash mvnw -B verify
bash mvnw -B -ntp test-compile dependency:build-classpath -Dmdep.includeScope=test -Dmdep.outputFile=target/test-classpath.txt
```

前端目录 `npm run build` 后，回到项目根目录：

```bash
# 本机Chrome路径；其他环境使用自己的Chrome／Chromium
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  .cache/mcp-phase1-venv/bin/python scripts/smoke-chat.py --admission --output .cache/new-admission-chain.json
```

该选项只在测试入口替换官网页面，生产启动入口不会读取测试开关来替换取证。报告路径必须未存在。日常启用须使用本轮Java／前端构建和已安装锁定依赖的Python，在原FastAPI启动进程的环境设置 `ADMISSION_MCP_ENABLED=true`，按原入口重新加载；`RAG_DATA`仍指向原获批语料，不因启用自动换资料、建索引或迁移。设回false并重新加载Python即可停用，已保存历史保留。本轮未执行日常启用。
