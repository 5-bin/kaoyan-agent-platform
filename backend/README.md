# 考研 Agent 后端

由原单模块后端拆分为 Maven 多模块工程，采用 Java 17 和 Spring Boot 3.5.16。多模块构建与本地演示链路已验证，范围见[验证记录](../docs/验证记录.md)；完整领域业务及容器验收仍待完成。

## 模块

- `kaoyan-common`：`course.kaoyan.common.exception` 下的通用异常、`course.kaoyan.common.enums` 下的领域枚举。
- `kaoyan-pojo`：`course.kaoyan.pojo.entity` 下的 JPA 实体、`course.kaoyan.pojo.dto` 下的 DTO 和接口契约，依赖 common。
- `kaoyan-server`：Web、Security、业务服务、Repository、Agent 调用、`handler` 统一错误处理和应用配置，依赖 common 与 pojo。

`pom.xml` 为父工程，打包类型为 `pom`；只有 server 模块生成 Spring Boot 可运行 JAR。应用入口是 `kaoyan-server/src/main/java/course/kaoyan/Application.java`，配置、静态页面和测试分别在该模块的 `src/main/resources/application.properties`、`src/main/resources/static/` 和 `src/test/java/`。

## 构建

从 `backend/` 目录执行，使用父工程构建全部模块：

```bash
./mvnw -B test
./mvnw -B package
```

Windows PowerShell 对应使用 `./mvnw.cmd -B test` 和 `./mvnw.cmd -B package`。Maven Wrapper 首次运行需要下载 Maven 与依赖；本地仓库路径由 `.mvn/maven.config` 配置。

打包产物为 `kaoyan-server/target/kaoyan-server-0.1.0.jar`，原来的 `target/kaoyan-agent-platform-0.1.0.jar` 不再是新结构的产物。

## 运行

先按[项目 README](../README.md)创建虚拟环境、初始化根目录 `.env` 并启动 Python Agent。另开终端，从项目根目录加载配置后运行已打包的 server：

```bash
set -a
. ./.env
set +a
cd backend
java -jar kaoyan-server/target/kaoyan-server-0.1.0.jar
```

Windows PowerShell 需先将根目录 `.env` 中的配置加载为进程环境变量，再进入 `backend/` 执行相同的 `java -jar` 命令；不要把 shell 的 `set -a` 当成 PowerShell 命令。

访问 [本地平台](http://127.0.0.1:8080)。默认 H2 路径相对于进程工作目录，以上方式使用 `backend/data/`；IDE 启动 `Application` 时同样将工作目录设为 `backend/` 并加载环境变量。不要切换到 server 目录启动而意外创建新库。

优先使用父工程打包后运行 JAR。`spring-boot:run` 只适用于 server 模块，不能直接对含 `common`、`pojo` 的整个构建反应堆执行；仅选 server 运行前还需使依赖模块在本地仓库可用。

## 配置与页面同步

- Java 与 Python 使用一致的 `AGENT_INTERNAL_KEY`，由根目录 `scripts/init-env.py` 生成或通过环境变量设置。不要依赖 Java 配置文件中的默认值，不在文档或日志中记录真实凭证。
- 数据库配置使用 `DB_URL`、`DB_USER`、`DB_PASSWORD`，Agent 地址使用 `AGENT_BASE_URL`；完整示例见根目录 `.env.example`。
- `frontend/` 与 server 的 `src/main/resources/static/` 当前各保存一份页面，POM 没有自动复制配置。修改前端需同步打包资源，重新构建后才会反映到 JAR 页面。
- `scripts/smoke.py` 和 `backend/Dockerfile` 已使用 server 的新 JAR 路径；Dockerfile 从父工程构建三个模块，构建上下文排除各模块 `target/`。实际联调结果与容器验证范围见[验证记录](../docs/验证记录.md)。
