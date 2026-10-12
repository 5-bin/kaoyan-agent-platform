# 考研 Agent 后端

由原项目后端功能等价迁移而来，采用 Java 17 和 Spring Boot 3.5.16。

## 模块

- `kaoyan-common`：通用异常、错误定义、领域枚举等无业务依赖代码。
- `kaoyan-pojo`：JPA 实体、DTO 和接口契约。
- `kaoyan-server`：Web、Security、业务服务、Repository、Agent 调用和应用配置。

## 构建

```powershell
.\mvnw.cmd clean test
```

## 运行

```powershell
.\mvnw.cmd -pl kaoyan-server -am spring-boot:run
```

## 本地 Agent 密钥

默认使用 `kaoyan-local-internal-key-2026`。如果要和 FastAPI 服务共享其他密钥，启动前设置：

```powershell
$env:AGENT_INTERNAL_KEY='至少16位ASCII字符'
```
