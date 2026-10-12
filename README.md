# 考研 Agent 平台

面向计算机考研／408的可运行模块骨架：原生Web前端 → Spring Boot业务后端 → FastAPI Agent。

## 当前能力

- 可用：注册、登录、退出、学生角色、按账号隔离的任务提交／历史、真实Java→Python调用、演示资料引用、任务限流及失败保存。
- 工程演示：四科各一段待审核资料，关键词检索，默认不调用模型；不是正式备考知识库或题库。
- 开发中：档案、院校数据、推荐记录、刷题批次、判分、错题、收藏、学习统计、管理员审核发布。对应控制器与DTO存在，合法请求返回`501 / FEATURE_NOT_IMPLEMENTED`；学生管理请求返回403。
- Python择校和错题流程有类型化入口，但返回unsupported。Java尚未构建经授权的档案／作答上下文，因此相关外部任务返回501，不创建假记录。

## 目录与文档

`frontend/`是同源页面；`backend/`是业务与权限；`agent/`是内部Agent；`scripts/`是配置与验证；`deploy/`和`compose.yaml`提供容器配置。

- [完整设计与开发阶段](考研Agent平台搭建文档.md)
- [当前接口与限制](docs/接口约定.md)
- [部署说明](docs/部署说明.md)
- [实际验证记录](docs/验证记录.md)
- [基础工程复用说明](docs/基础工程参考说明.md)
- [开发约定](AGENTS.md)

## 本地运行

需要JDK17—25、Python3.13；Maven Wrapper首次使用会下载依赖。前端无需构建工具，浏览器必须通过Java页面访问，不能直接打开HTML文件。

从项目根目录准备环境：

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r agent/requirements-dev.lock.txt
./.venv/bin/python scripts/init-env.py
```

该脚本只在.env不存在时生成内部凭证和数据库密码，默认`AGENT_MODE=demo`，不打印凭证。已存在配置会保留。

终端A，从项目根目录启动Python：

```bash
set -a
. ./.env
set +a
cd agent
../.venv/bin/python -m uvicorn agent_service.api:create_app --factory --host 127.0.0.1 --port 8001
```

终端B，从项目根目录构建并启动Java：

```bash
set -a
. ./.env
set +a
export MAVEN_USER_HOME="$PWD/.cache/maven"
cd backend
./mvnw -B package
java -jar target/kaoyan-agent-platform-0.1.0.jar
```

打开[本地平台](http://127.0.0.1:8080)，注册账号，进入“知识问答”，填入演示问题并提交，再查看“学习记录”。两终端使用Ctrl+C停止。Java数据库位于backend/data，每次仍从backend启动；不要删除数据库解决密码不一致。

## 验证

从项目根目录执行。Java测试用独立内存库，Python模型请求用Mock；不读取已有业务数据库或调用付费模型。

```bash
export MAVEN_USER_HOME="$PWD/.cache/maven"
(cd backend && ./mvnw -B test)
(cd agent && ../.venv/bin/python -m pytest -q)
./.venv/bin/python scripts/check-docs.py
./.venv/bin/python scripts/smoke.py --output docs/验证输出/新的冒烟报告.json
```

冒烟检查前需已有JAR；使用临时进程、随机端口与独立H2文件库，结束后关闭。报告已存在时拒绝覆盖。

浏览器检查另需Node和Playwright；可使用已安装的Playwright，通过`NODE_PATH`指定其包目录，并用`CHROME_PATH`指向Chrome可执行文件：

```bash
./.venv/bin/python scripts/smoke.py --output docs/验证输出/新的页面联调.json --browser-check --node node
```

该命令在临时后端上执行真实页面操作和迟到响应隔离检查，创建独立上下文，不读取日常浏览器数据。390宽度检查不是实机手机验收。CI默认执行Java、Python、语法、文档和离线链路检查，不依赖模型密钥。

## 模型与部署

已有chat/completions适配层，但真实供应商未验证。配置MODEL_BASE_URL、MODEL_API_KEY、MODEL_NAME并开启model会产生供应商请求；当前资料仍是未审核演示内容，不能据此声称正式领域能力。

容器、PostgreSQL和Caddy配置见[部署说明](docs/部署说明.md)。没有自动公开部署；应用网站的访问地址与GitHub仓库地址不同。

## 下一步

按完整设计逐步实现真实资料审核、中文BM25、档案与招生工具、刷题判分及批次保存；随后执行领域案例对比与公网验收。未新增项目开源许可证；Maven Wrapper保留其Apache许可头，第三方依赖遵循各自许可证。
