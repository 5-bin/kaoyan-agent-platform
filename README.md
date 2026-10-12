# 考研 Agent 平台

面向计算机考研／408的模块骨架：原生 Web 前端 → Spring Boot 业务后端 → FastAPI Agent。Java 后端现采用 Maven 多模块结构；历史骨架验证见验证记录，结构调整后的运行与联调需要重新验证。

## 当前能力

- 可用：注册、登录、退出、学生角色、按账号隔离的任务提交／历史、真实Java→Python调用、演示资料引用、任务限流及失败保存。
- 工程演示：四科各一段待审核资料，关键词检索，默认不调用模型；不是正式备考知识库或题库。
- 开发中：档案、院校数据、推荐记录、刷题批次、判分、错题、收藏、学习统计、管理员审核发布。对应控制器与DTO存在，合法请求返回`501 / FEATURE_NOT_IMPLEMENTED`；学生管理请求返回403。
- Python择校和错题流程有类型化入口，但返回unsupported。Java尚未构建经授权的档案／作答上下文，因此相关外部任务返回501，不创建假记录。

## 目录与文档

```text
考研agent平台搭建/
├── frontend/                         # 原生页面：index.html、app.js、style.css、js/api.js
├── backend/
│   ├── pom.xml                       # Maven 父工程，聚合三个模块
│   ├── mvnw / mvnw.cmd                # macOS/Linux 与 Windows 构建入口
│   ├── kaoyan-common/                 # 通用异常、领域枚举
│   ├── kaoyan-pojo/                   # JPA 实体、DTO 与接口契约
│   └── kaoyan-server/                 # Spring Boot 应用、业务服务与测试
├── agent/
│   ├── agent_service/                 # FastAPI、流程、检索、工具与模型适配
│   ├── knowledge/                     # 演示资料与来源元数据
│   ├── evaluation/                    # 评估脚本与案例
│   └── tests/                         # Python 测试
├── scripts/                           # 环境初始化、文档与联调检查
├── docs/                              # 接口、部署、验证与复用说明
├── deploy/                            # Caddy 配置
└── compose.yaml                       # 容器编排配置，结构适配待完成
```

后端依赖方向为 `kaoyan-pojo → kaoyan-common`，`kaoyan-server → kaoyan-pojo + kaoyan-common`。父工程只聚合构建，可运行 JAR 由 `kaoyan-server` 生成，详见[后端 README](backend/README.md)。

Java 启动入口为 `backend/kaoyan-server/src/main/java/course/kaoyan/Application.java`，配置在该模块的 `src/main/resources/application.properties`，测试在 `src/test/java/`。业务包包括 `auth`、`task`、`profile`、`catalog`、`practice`、`recommendation`、`study`、`admin`，统一错误处理在 `handler`。

Java 实际提供的页面位于 `backend/kaoyan-server/src/main/resources/static/`，与 `frontend/` 当前内容一致。现有 POM 没有从 `frontend/` 自动复制资源的配置，修改页面时需同步这两个位置，再重新打包。

- [完整设计与开发阶段](考研Agent平台搭建文档.md)
- [当前接口与限制](docs/接口约定.md)
- [部署说明](docs/部署说明.md)
- [实际验证记录](docs/验证记录.md)
- [基础工程复用说明](docs/基础工程参考说明.md)
- [开发约定](AGENTS.md)

## 本地运行

后端 POM 使用 Java 17 和 Spring Boot 3.5.16；Python 按现有锁文件与 CI 使用 3.13。Maven Wrapper 首次使用会下载依赖。前端无需构建工具，浏览器必须通过 Java 页面访问，不能直接打开 HTML 文件。

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
java -jar kaoyan-server/target/kaoyan-server-0.1.0.jar
```

打开[本地平台](http://127.0.0.1:8080)，注册账号，进入“知识问答”，填入演示问题并提交，再查看“学习记录”。两终端使用 Ctrl+C 停止。以上启动方式默认将 Java 数据库保存在 `backend/data/`；每次保持从 `backend/` 启动，不要删除数据库解决密码不一致。IDE 启动也需将工作目录设为 `backend/` 并加载相同环境变量，避免意外创建另一份数据库。

## 验证

从项目根目录执行。Java测试用独立内存库，Python模型请求用Mock；不读取已有业务数据库或调用付费模型。

```bash
export MAVEN_USER_HOME="$PWD/.cache/maven"
(cd backend && ./mvnw -B test)
(cd agent && ../.venv/bin/python -m pytest -q)
./.venv/bin/python scripts/check-docs.py
```

`scripts/check-docs.py` 检查文档链接、JSON 与部分静态配置，不验证 Maven 构建、Docker 镜像或业务运行。

**多模块适配待完成：** `scripts/smoke.py` 仍查找旧的 `backend/target/kaoyan-agent-platform-0.1.0.jar`，`backend/Dockerfile` 仍复制旧的 `backend/src/` 并引用旧 JAR。更新这些路径前，不能把以下冒烟命令或容器部署视为当前结构下可用的入口；CI 的链路检查也受此影响。

适配后的冒烟检查入口如下。检查前需已有新 JAR；脚本使用临时进程、随机端口与独立 H2 文件库，结束后关闭。报告已存在时拒绝覆盖。

```bash
./.venv/bin/python scripts/smoke.py --output docs/验证输出/新的冒烟报告.json
```

浏览器检查另需Node和Playwright；可使用已安装的Playwright，通过`NODE_PATH`指定其包目录，并用`CHROME_PATH`指向Chrome可执行文件：

```bash
./.venv/bin/python scripts/smoke.py --output docs/验证输出/新的页面联调.json --browser-check --node node
```

上述页面命令同样需先完成冒烟脚本适配。脚本在临时后端上执行真实页面操作和迟到响应隔离检查，创建独立上下文，不读取日常浏览器数据。390 宽度检查不是实机手机验收。现有 CI 配置包含 Java、Python、语法、文档和离线链路检查，不依赖模型密钥；历史通过记录不代表本次多模块结构已通过。

## 模型与部署

已有chat/completions适配层，但真实供应商未验证。配置MODEL_BASE_URL、MODEL_API_KEY、MODEL_NAME并开启model会产生供应商请求；当前资料仍是未审核演示内容，不能据此声称正式领域能力。

容器、PostgreSQL 和 Caddy 配置见[部署说明](docs/部署说明.md)，使用前需完成上述 Dockerfile 的多模块适配并重新验证。没有自动公开部署；应用网站的访问地址与 GitHub 仓库地址不同。

## 下一步

先完成冒烟脚本与 Dockerfile 的适配，并重新验证多模块构建和三层联调。`backend/.gitignore` 已通过 `**/target/` 排除各模块构建产物，交付时仍需检查实际文件清单。之后按完整设计逐步实现真实资料审核、中文 BM25、档案与招生工具、刷题判分及批次保存；随后执行领域案例对比与公网验收。未新增项目开源许可证；Maven Wrapper 保留其 Apache 许可头，第三方依赖遵循各自许可证。
