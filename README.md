# 考研 Agent 智能备考平台

当前代码使用 Vue 3 + TypeScript + Vite、Spring Boot 3.5 + MyBatis-Plus + JWT/OpenFeign、FastAPI + OpenAI 兼容客户端。业务数据库是 MySQL 8，Redis 用于令牌撤销。默认每账号每UTC日30项任务、每分钟6项，限额和任务记录持久保存；重启将遗留RUNNING标记为FAILED。单Python实例另有每UTC日100次模型尝试限额，进程重启会重置，不代替供应商的账单限额。目录为 `kaoyan-frontend/`、`kaoyan-B/`、`kaoyan-agent/`。

本次在独立 Git 工作树中基于远端 `a9200f9` 适配新框架，保留现有接口路径、MySQL 表及前端风格。修改范围、验证结果与剩余限制见[当前框架适配](docs/当前框架适配.md)。`docs/work.md`、`work1.md`、`work2.md`、`agent.md` 是历史生成提示词，不能当成运行记录；本文件和适配记录描述当前代码。

## 文档入口

- [项目协作规范](AGENTS.md)：AI 开发助手的阅读顺序、三端职责、接口协作、数据保护和验证约定。
- [完整平台搭建文档](考研Agent平台搭建文档.md)：需求、页面流程、当前架构与契约、待实现业务设计、开发阶段及运行验收入口。
- [当前框架适配与验收](docs/当前框架适配.md)：2026-10-14 框架适配的历史证据、测试环境和剩余限制。

搭建文档区分当前实现与建设目标；现有刷题和无检索模型回答尚未达到完整领域验收标准。历史提示词保留原位，其命令和操作要求不构成当前执行授权。

## 准备环境

需要 JDK 17、Python 3.12（本地验证见适配记录）、Node 20、MySQL 8、Redis。Maven Wrapper 已包含；首次构建下载依赖到项目 `.cache/`。不使用旧版 `backend/`、`agent/` 或 `frontend/` 命令。

从项目根目录执行：

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r kaoyan-agent/requirements-dev.txt
./.venv/bin/python scripts/init-env.py
```

在本地 `.env` 填入数据库账号密码、Redis 连接和可选模型／OSS配置。脚本只生成 JWT 和内部调用的随机凭证，不覆盖已有 `.env`。Java 与 Python 必须使用相同的 `AGENT_INTERNAL_KEY`。代码不提供可直接使用的默认签名密钥。

先由数据库负责人准备独立开发库。`kaoyan-B/src/main/resources/db/V1__init.sql` **包含 DROP TABLE**，仅可在明确可丢弃的空测试库初始化，不得在已有业务库直接重跑。其余种子脚本包含演示用户、题目和院校，来源与真实招生口径未验证，不自动执行或作为正式数据。本轮不改表、不执行迁移。

Python 当前只查询审核通过且启用的题目；建议为它设置仅有 question 表 SELECT 权限的数据库账号。未配置模型密钥时可以启动并检查健康接口，模型任务返回明确失败。OSS 未配置时核心服务可以启动，上传请求返回 503。

## 启动

macOS/Linux 的两个服务终端均先从项目根目录加载配置：

```bash
set -a
. ./.env
set +a
```

终端 A：

```bash
cd kaoyan-agent
# 如果使用独立只读账号，在此终端覆盖 DB_USER / DB_PASSWORD。
../.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

终端 B：

```bash
cd kaoyan-B
./mvnw -B package
java -jar target/kaoyan-backend-1.0.0.jar
```

终端 C：

```bash
cd kaoyan-frontend
npm ci
npm run dev
```

浏览器打开 [本地前端](http://localhost:5173)。Vite 将 `/api` 代理至 Java 8080，Java 通过内部凭证请求 Python 8001。数据库 3306、Redis 6379；内部服务不应直接暴露公网。前端打包后的 `/api` 反向代理需由部署环境配置，本轮未部署。

Windows 使用 `py -3.12 -m venv .venv`、`.venv\Scripts\python` 和 `mvnw.cmd`；需先将 `.env` 加载为进程环境变量，不能执行上述 Bash 的 `set -a`。可选后端覆盖模板为 `kaoyan-B/src/main/resources/application-dev.example.yml`，复制成已忽略的 `application-dev.yml` 后填写。

## 验证

以下验证不依赖真实模型或正式业务库：

```bash
(cd kaoyan-B && ./mvnw -B verify)
(cd kaoyan-agent && ../.venv/bin/python -m pytest -q)
(cd kaoyan-frontend && npm ci && npm run build)
./.venv/bin/python scripts/check-framework.py
```

本地已通过25项Java测试、33项Python测试、前端类型检查及生产构建，并通过15项HTTP链路检查（包含6项桌面浏览器操作）。链路使用真实Java/Python进程、H2、Redis及模型替身，迟到响应检查使用浏览器拦截模拟。本机JDK25编译目标17、Python3.13、Node24；不扩大为JDK17／Python3.12／Node20的本地验证。

可复现隔离HTTP检查：

```bash
(cd kaoyan-B && ./mvnw -B test-compile dependency:build-classpath -Dmdep.includeScope=test -Dmdep.outputFile=target/test-classpath.txt)
./.venv/bin/python scripts/smoke-current.py --output .cache/新的HTTP报告.json
```

增加 `--browser-check --node node` 可验证任务页面，需已有Chrome和Playwright；通过 `NODE_PATH` 指定Playwright包目录、`CHROME_PATH` 指定浏览器文件。脚本使用独立浏览器资料、随机端口，结束后关闭本次进程，报告存在时拒绝覆盖。`API_PROXY_TARGET` 只控制Vite开发代理的Java地址。

GitHub Actions 已切换到三个新目录，并加入真实Java→Python的隔离HTTP检查；配置更新不代表远端 CI 已运行。真实 MySQL/Redis 联调、实际后端浏览器操作、模型供应商、正式领域资料与公网验收的状态见[适配记录](docs/当前框架适配.md)。
