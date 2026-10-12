# 考研 Agent 平台开发约定

## 项目入口与边界

- 从[README](README.md)、[当前接口](docs/接口约定.md)、[搭建文档](考研Agent平台搭建文档.md)和[验证记录](docs/验证记录.md)了解当前版本；设计文档中的完整功能不等于已实现能力。
- 当前为模块骨架，Java 后端已调整为 Maven 多模块。账号、知识问答工程演示和任务历史属于已有实现；其他模块有契约但返回501。历史验证不能作为结构调整后的构建或联调证据，不得把待审核演示资料写成正式教材、题库或领域效果。
- 原生前端仅调用Java；Java负责认证、授权和个人记录；Python接收必要的类型化上下文，不直接修改业务库。模型不能授予权限、执行SQL或覆盖客观题答案。
- 修改接口同时检查Java DTO、Python模型、前端、保存结构及测试。任务状态、科目和刷题枚举以搭建文档为准。

## 目录与模块协作

- `backend/pom.xml` 是父工程，聚合 `kaoyan-common`、`kaoyan-pojo`、`kaoyan-server`；运行与构建入口见[后端 README](backend/README.md)。不再向旧的 `backend/src/` 添加代码。
- `kaoyan-common` 存放 `course.kaoyan.common.exception` 和 `course.kaoyan.common.enums` 下的通用异常、领域枚举，不依赖业务服务或持久化实现。
- `kaoyan-pojo` 存放 `course.kaoyan.pojo.entity` 下的 JPA 实体，以及 `course.kaoyan.pojo.dto` 下的 DTO／接口契约；依赖 common，不依赖 server。
- `kaoyan-server` 存放应用入口、Controller、Service、Repository、认证与 Agent 调用。按现有 `auth`、`task`、`profile`、`catalog`、`practice`、`recommendation`、`study`、`admin` 业务包组织，统一错误处理在 `handler`。
- 依赖方向保持 `pojo → common`、`server → pojo + common`。移动实体或修改公共枚举时检查跨模块 import、JPA 扫描、序列化与 DTO 校验；不要引入循环依赖。
- Java 配置在 `backend/kaoyan-server/src/main/resources/application.properties`，测试在该模块的 `src/test/java/`，可运行产物在该模块的 `target/`。新增依赖先判断所属模块，不把业务依赖全部放入父 POM 或 common。
- 前端编辑入口为 `frontend/`，Java 打包资源在 `backend/kaoyan-server/src/main/resources/static/`。当前没有自动同步配置，页面修改同步两处并检查内容一致；若新增构建同步机制，更新运行说明。
- `agent/agent_service/` 管 Python 服务与流程，`agent/knowledge/` 管演示资料，`agent/evaluation/` 管评估，`agent/tests/` 管测试。Java 模块拆分不改变前端 → Java → Python 的调用边界。

## 数据与资料

- 资料保留来源、定位、版本、获取日期和使用权限；缺资料时返回未覆盖，不编造招生事实、题目出处或引用。
- 招生数据不能跨年份、专业或统计口径混用；题库须审核后发布。参考网站的登录后能力未验证，未经许可不抓取题目和教材。
- 正式刷题批次由服务器固定题目版本和顺序，记录账号归属；草稿不计作答，重复提交不重复判分，提示辅助与独立作答分开统计。
- 模块占位服务不写业务数据。新增正式实现时替换占位服务，增加权限、持久化及失败测试，不能只把501改成200。

## 运行、配置与验证

- 密钥只使用环境变量，`.env`、数据库、缓存、虚拟环境和原始测试截图不提交。不要输出真实凭证或复制其他项目的数据。
- 本地按 README 从 `backend/` 构建并启动 `kaoyan-server/target/kaoyan-server-0.1.0.jar`，保持同一数据库路径；IDE 工作目录也设为 `backend/`。复用虚拟环境可以用于验证，但仓库运行说明必须支持独立创建环境。
- Java 与 Python 必须显式加载同一份环境配置，内部凭证通过 `scripts/init-env.py` 生成或环境变量提供。配置中现有的 Java 默认值不能代替双端配置，不在文档中传播该值。
- 修改 Java 后在 `backend/` 运行 `./mvnw -B test`，覆盖三个模块；Windows 使用 `mvnw.cmd`。打包在父工程执行 `./mvnw -B package`，不要对所有模块直接执行 `spring-boot:run`。修改 Python 后在 `agent/` 运行 `../.venv/bin/python -m pytest -q`。纯文档修改检查链接、路径和 JSON，不跑无关服务。
- 完整链路使用 `scripts/smoke.py` 的临时端口与独立数据库；脚本与 Dockerfile 使用 `backend/kaoyan-server/target/kaoyan-server-0.1.0.jar`。调整模块或产物名称时同步两处路径、README 与验证记录，不能通过复制旧 JAR 制造通过记录。Docker 构建上下文继续排除各模块 `target/`。
- 页面验证使用隔离浏览器上下文，不读取日常浏览器资料。实际用例与限制写入验证记录；文档静态检查通过不等于链路、容器或公网验收通过。
- 模型测试默认模拟，不产生付费调用；真实模型评估和公开部署按用户当前授权范围执行。容器配置存在不代表PostgreSQL或公网已经验证。
- 当前仅单Java和单Python实例；管理员权限由服务端控制，公开注册不能选择管理员。

## 协作与交付

- 保留现有文件和用户修改，仅处理当前任务范围。Git操作前检查差异，上传前核对文件清单、忽略规则及秘密信息；多模块下分别检查各模块的 `target/`，不要只依赖旧的 `backend/target/` 忽略项，不提交 `.idea/` 本机配置；不强制覆盖远端。
- 文档区分历史验证、当前验证和未运行事项。完成后报告真实结果、仓库链接与剩余工作，不虚构访谈、团队身份或课程成绩。
