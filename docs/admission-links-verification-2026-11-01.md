# 招生 MCP 仅返回网址：实现与验证

本文 `.cache/` 下的日志与截图仅供本机追溯，不随公开仓库分发。

日期：2026-11-01。当前契约见[搭建文档](../考研Agent平台搭建文档.md#招生官网网址契约2026-11-01替代自动核验)，运行入口见[README](../README.md#可选招生官网链接-mcp)。首次实施只完成隔离验证；本机日常服务按用户后续授权重启，范围见文末记录。

## 实现与兼容

- 招生 stdio MCP 仅公开 `get_admission_links({schoolCode})`，返回登记院校、登记年份与完整有序网址。10校原有 `code/name/hosts/entries/year` 逐项保持一致，删除原抓取查询、表单与解析配置。查询不依赖同年语料基线，不执行 DNS、HTTP、HTML／PDF解析或模型请求。
- 内部计划使用 `ADMISSION_LINKS` 与 `admissionLinks`；SCHOOL专家继续使用真实HelloAgents工具适配。输入只需一个登记院校，旧核对问法转换为链接查询；无年份／专业不再追问。模型不能生成旧或新的招生动作，旧预备计划安全降级为澄清。每轮一次、查询5秒、发现10秒，取消、关闭、独立故障与健康状态保持原边界。
- Python客户端与Java独立校验完整结构、院校名称、登记年份及有序网址，拒绝额外参数、未知工具、未知院校及伪造结果。非法输入不占调用预算，工具关闭／失败明确返回`UNSUPPORTED`，不静默转为本地成功。
- 页面及Word／PDF／Markdown导出只提供安全登记网址，注明登记年份不代表当前或最新招生年度，请用户自行确认招生年份、专业及报考条件。历史`admissionCheck`不改写；显示、导出与后续模型历史忽略原核验结论和证据。复合结果中的结构化院校候选保留，未知院校不展示旧记录带入的网址。
- 删除招生爬取、HTML/PDF解析、工作进程、诊断及专用旧测试夹具，移除`pdfplumber`依赖声明。知识MCP、审核语料、releaseId、规则择校、公开任务类型与持久化职责保持原契约。无数据库迁移。

关键实现：[MCP入口](../kaoyan-agent/admission_mcp_server.py)、[Java校验与历史投影](../kaoyan-B/src/main/java/com/kaoyan/service/AdmissionLinksValidator.java)、[网址卡片](../kaoyan-frontend/src/components/AdmissionLinksView.vue)、[导出内容](../kaoyan-B/src/main/java/com/kaoyan/export/ExportSources.java)。

## DeepSeek Harness 与审查

按用户要求实际调用本机DeepSeek Harness 0.2.1-rc.5配套CLI，使用已有`deepseek-account / deepseek-flash`配置完成隔离副本中的代码生成。只复制必要源码和测试，不复制`.env`、凭证、数据库、上传数据、依赖环境、构建产物或业务缓存；认证由Harness管理，未输出凭据。

合入前以文件哈希检查工作树相对隔离副本基线没有并发变化，只应用本任务差异，原文件保留在本地忽略的备份中。Codex审查并修正了单校／多校识别、Java降级与澄清授权、非法院校预算、旧结果投影、名册网址白名单、导出超链接及异常字段展示，并补充独立验收测试。Harness代码生成不等于业务模型或招生信息效果验证。

## 实际验证

环境：macOS，Python3.13，复用本项目`.cache/mcp-pdf-venv`及已有依赖；HelloAgents0.2.8、OpenAI SDK1.109.1、MCP1.12.4。Java运行时25.0.4.1、编译目标17；Node22.23.3；Chrome独立测试上下文。未安装、升级或卸载已有环境中的包。

| 检查 | 实际结果与范围 |
| --- | --- |
| Python全量pytest | **433项通过**，55.12秒；覆盖知识检索、规则择校、原Agent流程及新招生链接。保留2条Pydantic／Starlette弃用提示。 |
| 真实stdio清单检查 | **10校通过**，返回值与登记清单逐项一致；最终健康READY，单次协议调用观测2—3毫秒，不作为官网速度或领域效果指标。默认离线检查也通过。 |
| 禁网与框架测试 | 真实子进程在DNS、外网连接、HTTP及旧解析模块导入被禁止时，仍完成10校查询；工具发现、HelloAgents适配、非法参数／伪造链接拒绝、预算、超时、取消、关闭及故障隔离通过。 |
| Java verify | **203项中201项通过、2项跳过**，BUILD SUCCESS，57.438秒；使用隔离H2、Redis／供应商替身和真实Python子进程。2项真实Redis导出集成测试因未设置`KAOYAN_EXPORT_REDIS_TEST`跳过，未连接日常Redis代替验收。 |
| 三格式导出 | 旧核验结论、通知、差异、摘录及不可信网址不出现在生成的Word、PDF、Markdown中；实际检查Word超链接、PDF链接注释、Markdown链接及中文可读文本。复合候选保留，原结果对象不改写。 |
| 前端生产构建 | Vue／TypeScript检查及Vite构建通过，保留已有大包体提示。 |
| Playwright回归 | **40项通过**，29.7秒；1280桌面与390手机视口，模拟API，覆盖新旧招生历史、危险／畸形链接、名册链接、复合候选、导出、聊天及推荐。不是实机手机验收。 |
| 真实三端隔离链路 | **11项通过**：真实Vue→Java→FastAPI→stdio MCP，独立临时H2及Redis／供应商替身；两种宽度检查实际网址、刷新恢复、无横向溢出和跨账号404，实际重启本次Java验证聊天及招生网址保留。结束后清理本次临时进程与数据。 |
| 静态核对 | 登记网址与年份保持、旧抓取实现不可达、历史文档替代标注、路径／锚点及`git diff --check`通过。 |

验证中修复了名称重复识别、礼貌前缀误判及单校“什么”问题被当成范围询问；Java正常降级不再因缺少链接被误判为协议失败，澄清也不能夹带未经本轮查询授权的链接。Node22下测试的JSON加载方式已修正。初次Chrome在沙箱内启动失败，随后在获准的独立测试上下文中通过，未使用日常浏览器资料。

复现命令（报告路径必须尚不存在）：

```bash
# 项目根目录：完整Python及默认离线／真实本地MCP检查
.cache/mcp-pdf-venv/bin/python -m pytest -q kaoyan-agent/tests
.cache/mcp-pdf-venv/bin/python scripts/check-admission.py
.cache/mcp-pdf-venv/bin/python scripts/check-admission.py --mcp --output .cache/new-admission-links.json

# kaoyan-B目录；当前mvnw未设执行位，保留原权限，通过bash调用相同包装脚本
PYTHON_EXECUTABLE="$PWD/../.cache/mcp-pdf-venv/bin/python" bash mvnw -B verify
bash mvnw -B test-compile dependency:build-classpath -Dmdep.includeScope=test -Dmdep.outputFile=target/test-classpath.txt

# kaoyan-frontend目录；Chrome路径可替换为本机测试浏览器
npm run build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm run test:e2e -- admission.spec.ts export.spec.ts multiagent.spec.ts recommendation.spec.ts conversation.spec.ts

# 项目根目录：上述构建与测试类路径准备好后运行；仅使用隔离服务
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' .cache/mcp-pdf-venv/bin/python scripts/smoke-chat.py --admission --output .cache/new-admission-chain.json
```

本地忽略的实际产物：Python最终日志（本机 `.cache/admission-links-harness-20261101/python-final.log`）、Java日志（本机 `.cache/admission-links-harness-20261101/java-verify.log`）、浏览器日志（本机 `.cache/admission-links-harness-20261101/browser-verified.log`）、MCP报告（本机 `.cache/admission-links-harness-20261101/final-mcp-report.json`）、三端报告（本机 `.cache/admission-links-harness-20261101/three-end-report.json`）。390宽度截图（本机 `.cache/admission-browser-1793523791792513000/admission-390.png`）已查看，网址换行与卡片显示正常；这些产物不随源码分发。

## 生效边界与未运行项

首次实施未修改真实`.env`、用户授权或日常业务记录，未迁移数据库、重启日常服务、创建分支、提交、推送或部署。随后用户另行授权重启，结果见下文。

日常MySQL／Redis集成、真实业务模型、官网可访问性／当年内容核实、Windows、手机实机和公网部署均**未运行**。招生内容由用户打开官方网址自行确认；登记年份和网址的存在不构成最新招生事实或招生资格确认。

## 日常三端重启（后续授权，2026-11-01）

按用户“帮我重启”的后续授权，确认现有三个监听进程的工作目录属于本项目后，分别正常停止，并按Python Agent、Java、Vite前端的顺序重新启动；MySQL和Redis原进程保持运行。Java沿用原有进程环境和新构建JAR，Agent使用本项目`.cache/mcp-pdf-venv`，前端沿用原启动参数。仅为本次Agent进程设置`ADMISSION_MCP_ENABLED=true`，未修改根`.env`；后续重启仍需显式设置该开关。

重启后实际检查：Python `/health`返回200，`mcpTools.admission`为`READY`，模型配置仍为启用；Java受保护接口无令牌返回401，前端首页返回200，新招生链接组件可由Vite提供。向本机Agent内部接口发送不含个人信息的“查官网南京审计大学”合成查询，计划为`ADMISSION_LINKS`、结果为`COMPLETED`并返回2个登记网址，没有`admissionCheck`字段；该直接内部查询不写Java业务记录、不访问院校网站、不调用模型。此次没有使用真实账号进行页面操作，不能将端口与内部查询检查扩大为日常业务端到端验收。
