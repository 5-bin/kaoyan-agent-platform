# 考研 Agent 智能备考平台

Vue 3 / TypeScript → Spring Boot 3.5 / MyBatis-Plus / MySQL → FastAPI RAG。Redis用于JWT注销撤销，是Java业务接口的运行依赖。

当前整合同学的框架适配（上游main `6383c92`）与RAG工作流。保留实时账号状态／角色检查、Redis注销撤销、分页参数兼容和隔离HTTP检查。

本轮实现内部接口加固、408与院校独立检索副本、确定性择校、场景识别及可选LLM解释。具体协议、验收和限制见 [RAG说明](docs/rag.md)。`docs/work*.md`、`docs/agent.md` 是历史生成提示词，不是当前运行说明。

## 文档入口

- [完整平台搭建文档](考研Agent平台搭建文档.md)：需求、当前契约与后续建设目标。
- [框架适配历史记录](docs/当前框架适配.md)：同学在合并前的验证与限制。
- [合并审查记录](docs/merge-review-2026-10-14.md)：本次冲突处理和重新验证范围。
- [RAG详细契约](docs/rag.md)：资料、筛选、快照、引用与版本。
- [PR #8修复验证](docs/pr8-fix-verification-2026-10-15.md)：删除后的配额、历史快照及页面联调修复。
- [Issue #9验证记录](docs/practice-answer-safety-verification.md)：学生答案隐藏、服务端判分展示与历史回顾安全。
- [Issue #11录题与审核验证](docs/question-entry-review-verification.md)：来源登记、审核流程及V9迁移边界。

## 当前能力

- `/internal/rag/chat`：内部凭证认证、任务枚举、输入上限、类型化上下文、结果和引用校验。
- 408：4段带来源的概念摘要，默认离线词项检索；可启用中文Embedding＋持久化Qdrant。覆盖范围较小，未覆盖时明确返回。
- 院校：3所学校的6条2027年普通全日制081200/085404资料。按年份、专业、学位、地区、学习方式与考试科目筛选，最多5个候选；不估计录取概率。
- AI：默认关闭。启用后解释候选或回答资料覆盖的问题；模型异常时保留规则结果，来源编号经过程序校验。
- 总结：Java只传本人已判分、带题目版本快照的有效作答，Python不连接业务数据库。
- 刷题：学生抽题／详情隐藏答案；提交后展示Java判分，回顾／错题／收藏仅显示本人有效作答快照。回顾可继续作答，旧快照无选项时仍展示已保存答案；明确不可用题目提示后跳过，网络失败可重试。跳过仅影响页面导航，不修改作答或统计；旧快照缺失不按当前题目补造。
- 推荐与任务共享任务表保存快照、来源、版本和结果；历史推荐不随档案更改。
- 管理员可在`/admin/questions`录入单选题、登记来源和使用权限、查看详情、补充未发布题并通过或驳回。新题先待审核；真题必须登记年份和原题号。支持对已审核题目停用和重新启用，保留题目与历史作答；编辑、审核及启停均校验版本，过期请求409。批量导入及完整题目版本发布后续建设。

旧院校列表的2025年估计值仍是演示数据，界面已标注，**不参与新推荐**。本轮未改造整个刷题/管理/认证系统，也不代表公网部署验收。

## 准备环境

需要 Java 17、Python 3.13、Node.js 22（含 npm）；业务运行另需 MySQL 8 和 Redis。

从根目录执行（Windows PowerShell）：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r kaoyan-agent/requirements-dev.txt
.\.venv\Scripts\python.exe scripts/init-env.py
```

所有服务使用根目录 `.env`。脚本生成随机内部凭证与JWT签名密钥，不覆盖已有文件、不打印凭证。填写自己MySQL的 `DB_USER`、`DB_PASSWORD` 及 Redis 的 `REDIS_HOST`、`REDIS_PORT`、可选 `REDIS_PASSWORD`，不要沿用历史代码中的密码。Redis不可用时受保护接口会失败，不能通过关闭注销撤销来绕过。Python自动读取根 `.env`；Java由启动脚本显式加载。OSS可不配置，未配置时文件接口返回503，不阻止核心服务启动。

### 数据库

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

## 启用中文向量检索

默认 `RAG_BACKEND=lexical`，不用下载权重即可检查规则、来源和页面。向量模式使用已实现的Qdrant＋FastEmbed，**不是把词项检索冒充Embedding**。

```powershell
cd kaoyan-agent
..\.venv\Scripts\python.exe ingest.py
```

该命令首次下载 `BAAI/bge-small-zh-v1.5` 中文模型，建立与语料及模型绑定的不可变集合；不调用付费LLM。然后把根 `.env` 中 `RAG_BACKEND` 改为 `qdrant`，重启Agent。

默认独立Qdrant数据库位于 `kaoyan-agent/.cache/rag/qdrant`，无需Docker。**本地模式仅单进程使用**：先停止Agent再导入。部署独立Qdrant服务时设置 `QDRANT_URL`、`QDRANT_API_KEY`；导入和服务需要相同资料、模型与索引标记目录。语料变更需先导入，再切换服务版本；缺少就绪标记不会返回部分索引。旧集合保留供回滚，不自动删除历史版本。

## 启用AI解释

在根 `.env` 填写供应商 `LLM_API_KEY`、HTTPS `LLM_BASE_URL`、模型名称，再设置 `LLM_ENABLED=true`。这将产生外部请求与可能的费用。代码默认关闭SDK重试，单次20秒、全流程42秒；Java读45秒、浏览器55秒。

每日模型次数是单Python进程内的限制，重启会重置，不能代替供应商预算。真实供应商和内容效果需另行验收。自动路由只对 `CHAT` 生效，不改变明确指定的任务；AI不负责判分或授予权限。

## 验证

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

Java测试在独立H2库启动真实Python子进程，不读日常MySQL，也不调用模型；子进程结束后清理。浏览器测试使用隔离上下文和模拟API，验证页面、历史显示、来源、文本安全和390宽度；不等于整站真实手机验收。

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
