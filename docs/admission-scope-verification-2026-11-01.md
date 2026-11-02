# 招生官网查询范围扩展验证

本文 `.cache/` 下的日志与截图仅供本机追溯，不随公开仓库分发。

日期：2026-11-01。用户确认将截图中的10校查询范围扩展到院校库全部学校。当前登记121校，新增111校，包括北京大学、清华大学。契约见[搭建文档](../考研Agent平台搭建文档.md#招生官网网址契约2026-11-01替代自动核验)，运行入口见[README](../README.md#可选招生官网链接-mcp)。

## 范围与来源

以当天已保存的[121校快照](../outputs/school-enrichment-20261101/final/school-levels.csv)为范围，本次不连接业务数据库。使用 Exa Search 逐校检索官方研究生招生／研究生院入口，对迁站、非HTTPS结果和访问受限入口追加查询及读取；仅保存机构名称、网址与核对说明，不复制招生正文或个人名单。逐校结果见[可读清单](admission-source-catalog-2026-11-01.md)及[结构化清单](admission-source-catalog-2026-11-01.json)。原始检索收据在本机忽略的`.cache/admission-scope-20261101/`中。

- 原10校的代码、名称、域名、完整有序网址和登记年份逐项保持一致，本轮逐校重新核对官网归属；原年度深链接未逐条重新取证。
- 新增111校使用官方HTTPS入口。南京师范大学旧官网明确说明迁站至`https://yjszs.njnu.edu.cn/`，研招网校方联系方式亦确认；新站及安徽大学门户本次读取受412限制。安徽大学域名由校方公开发布文件及已有采集来源核对，不复制文件中的名单。
- 浙江大学、武汉理工大学、云南大学的研究生专站HTTPS连接或证书检查失败，登记本次可读取的学校HTTPS主页作为导航，页面说明进入研究生招生栏目继续查阅。未将HTTP自动替换为未经确认的HTTPS，未关闭证书校验。
- 2027是入口登记所面向的报考年度，不表示当前网页已经完成年度内容核验。此改动只扩大链接清单，不改变审核RAG、releaseId、院校指标、推荐候选或业务数据。

## 实现与兼容

共享[登记表](../config/admission-sources.json)继续供Python MCP、Java严格校验与前端构建读取。Python与Java按完整校名优先遮蔽名称，解决“中国矿业大学（北京）”同时命中“中国矿业大学”的误判；兼容中英文括号，单独提到两校时仍须澄清，不能将两个招生主体合并。

缺院校或未知院校时给出登记数量与完整范围问法，不再把121校塞进1000字符的澄清字段。范围回答保留全部院校、登记年份与有序网址，使用短链接标签，实际8234字符，低于既有20000字符结果上限。模型、工具预算、取消与关闭、SSE、任务终态、历史投影及导出契约不变。未知院校测试改用独立未登记代码，不能继续把北京大学或清华大学作为负例。

隔离三端脚本新增`--admission-school`参数，默认仍为`nau`；本次使用`pku`，页面、历史及重启检查均采用北京大学真实登记入口。

## 实际验证

macOS、Python3.13、本项目`.cache/mcp-pdf-venv`，HelloAgents0.2.8／OpenAI1.109.1；Java25.0.4.1编译目标17，Node22、Chrome独立上下文。未安装或升级依赖。

| 检查 | 本次实际结果与边界 |
| --- | --- |
| 清单对照 | 121校名称与已保存院校库快照完全一致，逐校ID对应，原10校配置未改；Java JAR中的登记表与仓库源文件逐字节一致。 |
| Python全量pytest | 556项通过，69.73秒，保留2条既有弃用提示；包含121校确定性路由、中英文括号、多校拒绝、预算与禁网协议测试。随后将真实SSE用例扩展至南京审计／北大／矿大北京／浙大，4项通过，1.98秒；两次结果不相加作为全量总数。 |
| 真实stdio MCP检查 | 121校全部返回与登记表一致的结果，最终READY；观测单次3—72毫秒，仅为本地协议耗时，不是官网访问速度。禁DNS、外网连接、HTTP与旧解析模块的子进程测试覆盖全量清单。 |
| Java verify | 209项，207通过、2跳过，0失败／错误，BUILD SUCCESS，约63秒；覆盖全清单计划与结果校验、跨招生主体拒绝、历史及导出。2项真实Redis导出测试未启用，未连接日常Redis替代。 |
| 前端生产构建 | Vue／TypeScript与Vite构建通过，保留已有包体大小提示。 |
| Playwright | 26项通过，20.4秒；1280与390视口，模拟API，覆盖北大／矿大北京／浙大卡片、刷新、伪造与未知网址、新旧历史及导出。首次Chrome在沙箱内被操作系统中止，随后在获准的独立临时浏览器上下文重跑通过。 |
| 北京大学真实隔离三端 | 11项通过；实际Vue→Java→FastAPI→本地stdio MCP，问题为“帮我查询北京大学招生信息”，两种宽度检查登记链接、刷新恢复、无横向溢出及跨账号404；重启本次测试Java后记录与链接保留。使用临时H2及Redis／模型替身，结束后清理测试进程与临时数据。 |
| 静态检查 | JSON、来源表、路径及`git diff --check`通过。 |

首次回归发现新未登记测试校名含“示例”，命中已有示例排除规则；已改为“未登记测试大学”后重跑通过，没有放宽业务路由或修改排除规则。

本机复现命令（输出文件必须尚不存在）：

```bash
.cache/mcp-pdf-venv/bin/python -m pytest -q kaoyan-agent/tests
.cache/mcp-pdf-venv/bin/python scripts/check-admission.py --mcp --output .cache/new-admission-scope.json
# 从kaoyan-B执行；mvnw原权限不变，使用相同包装器
PYTHON_EXECUTABLE="$PWD/../.cache/mcp-pdf-venv/bin/python" bash mvnw -B verify
# 从kaoyan-frontend执行
npm run build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npx playwright test tests/admission.spec.ts tests/export.spec.ts
# 回到根目录，先按README准备target/test-classpath.txt
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' .cache/mcp-pdf-venv/bin/python scripts/smoke-chat.py --admission --admission-school pku --output .cache/new-pku-chain.json
```

本机日志与报告：`.cache/admission-scope-20261101/python-pytest.log`、`python-sse-final.log`、`mcp-report.json`、`java-verify-final.log`、`frontend-build.log`、`browser-tests-final.log`、`pku-isolated-chain.json`。这些本机报告不作为运行依赖。

本次隔离页面截图：1280桌面（本机 `.cache/admission-browser-1793532073185569000/admission-1280.png`）、390视口（本机 `.cache/admission-browser-1793532073185569000/admission-390.png`）。桌面截图已实际打开检查，包含截图原问题及北京大学官网链接；浏览器数据属于独立合成测试账号。

## 生效与未运行项

首次交付完成代码、Java JAR与前端构建，未自动启停日常服务。随后用户明确选择“现在重启三端并验证生效”，已核对三个监听进程均属于本项目并正常终止，依次启动Agent8001、Java8080、前端5173，加载新版121校登记表。原进程环境只在内存中保留，没有写出或打印凭证；招生MCP继续启用，模型开关及RAG版本保持一致，MySQL和Redis监听进程未改变。没有运行数据库脚本或迁移。

重启后实际检查：Agent健康200、招生MCP为READY；Java受保护接口及前端代理无令牌返回401，前端页面和新版链接组件200，Vite提供的121校完整登记表与仓库配置一致。向实际Agent内部计划／SSE接口发送北大、清华、矿大北京3条无个人上下文、明确禁止模型外发的合成查询，均为`ADMISSION_LINKS`、`COMPLETED/rules`，完整有序链接与登记表一致，没有`admissionCheck`。直接内部检查未经过Java，不创建测试账号或业务任务；未进行登录后的日常页面操作。旧回答不会因清单更新自动重新生成，需刷新页面并重新发送查询。

本次重启结果在本机运行摘要（本机 `.cache/admission-scope-20261101/daily-runtime/result.json`），对应私密日志位于同目录。初次预检发现Agent凭证由既有dotenv配置加载而非进程环境提供，预检时未停止任何进程；调整为仅在内存读取现有配置后，重启与检查成功。

业务MySQL维护写入／迁移、日常账号页面操作、真实供应商模型、全部官网逐链接持续访问、年度招生事实审核、真实Redis导出测试、实机手机、公网部署均未运行。官网查询返回链接，不恢复招生网页抓取或事实自动核验。

## 后续按用户指令关闭服务

同日用户要求关闭当前项目、MySQL、Redis及MCP。核对工作目录与监听进程后，正常停止前端5173、Java8080、Agent8001，Agent管理的招生MCP及前端构建子进程已退出；随后通过Homebrew停止`mysql@8.4`和`redis`服务，避免管理器自动拉起。核验五个端口均无监听、数据库及项目MCP进程无残留，两项Homebrew服务均已卸载运行任务。未强制杀进程、删除数据或修改根`.env`，未停止Codex应用工具进程。当前日常服务为关闭状态，先前重启验证保留为历史记录。本机停机摘要（本机 `.cache/admission-scope-20261101/shutdown.json`）记录实际核验结果。
