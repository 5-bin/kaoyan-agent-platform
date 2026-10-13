# 考研 Agent 平台

面向计算机考研／408的学习平台：原生 Web 前端 → Spring Boot 业务后端 → FastAPI Agent。Java 后端采用 Maven 多模块结构；冒烟脚本和 Dockerfile 已同步到新结构，实际验证范围见[验证记录](docs/验证记录.md)。

## 当前能力

- 可用：注册、登录、退出、学生角色、按账号隔离的任务提交／历史、真实Java→Python调用、演示资料引用、任务限流及失败保存。
- 刷题闭环：题目目录与筛选、章节／随机／错题／收藏组题、批次续做、草稿版本冲突、两级提示、收藏、服务端确定性判分、幂等提交、错题归集与掌握状态、结果页和学习统计。
- 工程演示数据：四科各一段待审核知识资料，以及四科共12道自编单选题。演示题用于验证交互与业务规则，仍需课程资料负责人复核，不能称为正式真题或正式题库。
- 开发中：档案、院校数据、推荐记录、管理员审核发布、题目撤回／版本迁移，以及生成式错题辅导。对应未实现接口仍返回`501 / FEATURE_NOT_IMPLEMENTED`；学生管理请求返回403。
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
└── compose.yaml                       # 容器编排配置，容器运行待验证
```

后端依赖方向为 `kaoyan-pojo → kaoyan-common`，`kaoyan-server → kaoyan-pojo + kaoyan-common`。父工程只聚合构建，可运行 JAR 由 `kaoyan-server` 生成，详见[后端 README](backend/README.md)。

Java 启动入口为 `backend/kaoyan-server/src/main/java/course/kaoyan/Application.java`，配置在该模块的 `src/main/resources/application.properties`，测试在 `src/test/java/`。业务包包括 `auth`、`task`、`profile`、`catalog`、`practice`、`recommendation`、`study`、`admin`，统一错误处理在 `handler`。

Java 实际提供的页面位于 `backend/kaoyan-server/src/main/resources/static/`，与 `frontend/` 当前内容一致。现有 POM 没有从 `frontend/` 自动复制资源的配置，修改页面时需同步这两个位置，再重新打包。

- [完整设计与开发阶段](考研Agent平台搭建文档.md)
- [刷题与错题接口、依赖和验收](docs/刷题与错题功能说明.md)
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

打开[本地平台](http://127.0.0.1:8080)，注册账号后可进入“知识问答”，也可在“刷题中心”创建练习、保存草稿、查看提示与判分，再到“错题本”和“学习记录”查看归集与统计。两终端使用 Ctrl+C 停止。以上启动方式默认将 Java 数据库保存在 `backend/data/`；每次保持从 `backend/` 启动，不要删除数据库解决密码不一致。IDE 启动也需将工作目录设为 `backend/` 并加载相同环境变量，避免意外创建另一份数据库。

## 验证

从项目根目录执行。Java测试用独立内存库，Python模型请求用Mock；不读取已有业务数据库或调用付费模型。

```bash
export MAVEN_USER_HOME="$PWD/.cache/maven"
(cd backend && ./mvnw -B test)
(cd agent && ../.venv/bin/python -m pytest -q)
./.venv/bin/python scripts/check-docs.py
```

`scripts/check-docs.py` 检查文档链接、JSON 与部分静态配置，不验证 Maven 构建、Docker 镜像或业务运行。

冒烟脚本读取 `backend/kaoyan-server/target/kaoyan-server-0.1.0.jar`，检查前需先在 `backend/` 执行 `./mvnw -B package`。脚本使用临时进程、随机端口与独立 H2 文件库，结束后关闭；不会启动日常开发服务或修改已有业务库。报告已存在时拒绝覆盖。

```bash
./.venv/bin/python scripts/smoke.py --output docs/验证输出/新的冒烟报告.json
```

浏览器检查另需Node和Playwright；可使用已安装的Playwright，通过`NODE_PATH`指定其包目录，并用`CHROME_PATH`指向Chrome可执行文件：

```bash
./.venv/bin/python scripts/smoke.py --output docs/验证输出/新的页面联调.json --browser-check --node node
```

脚本在临时后端上执行真实页面操作和迟到响应隔离检查，创建独立上下文，不读取日常浏览器数据。390 宽度检查不是实机手机验收。现有 CI 配置包含 Java、Python、语法、文档和离线链路检查，不依赖模型密钥；每次结果以对应提交的实际运行记录为准。

## 模型与部署

已有chat/completions适配层，但真实供应商未验证。配置MODEL_BASE_URL、MODEL_API_KEY、MODEL_NAME并开启model会产生供应商请求；当前资料仍是未审核演示内容，不能据此声称正式领域能力。

Dockerfile 已改为复制三个模块并构建 server JAR，构建上下文排除各模块 `target/`。容器、PostgreSQL 和 Caddy 配置见[部署说明](docs/部署说明.md)；本次未运行容器验收。没有自动公开部署；应用网站的访问地址与 GitHub 仓库地址不同。

## 下一步

在具备 Docker 的环境验证多模块镜像与 PostgreSQL 联调。`backend/.gitignore` 已通过 `**/target/` 排除各模块构建产物，交付时仍需检查实际文件清单。之后按完整设计逐步实现真实资料与题目审核、中文 BM25、档案与招生工具、题目发布版本和生成式错题辅导；随后执行领域案例对比与公网验收。未新增项目开源许可证；Maven Wrapper 保留其 Apache 许可头，第三方依赖遵循各自许可证。
