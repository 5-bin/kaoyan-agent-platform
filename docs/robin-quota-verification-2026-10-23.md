# robin 账号额度豁免验证（2026-10-23）

- Java 通过认证账号 ID 查询当前数据库用户名，精确匹配 `QUOTA_EXEMPT_USERNAME`；默认 robin，空值关闭。不接受前端豁免参数。
- 豁免每日／分钟任务额度，通过内部认证请求的 `quotaExempt` 字段传递给 Python。Python 跳过每日模型预算且不消耗其他账号的预算；单请求调用上限、超时、权限和隐私检查仍有效。
- `PYTHON_EXECUTABLE=<项目>/.cache/chat-venv/bin/python bash mvnw -B verify`：88 项通过，打包成功。首轮未指定完整 Python 环境导致集成环境启动失败；随后发现一项权限检查顺序回归，修正后上述完整验证通过。
- `.cache/chat-venv/bin/python -m pytest -q`（在 kaoyan-agent 下使用相对路径 `../.cache/chat-venv/bin/python`）：136 项通过。旧 .venv 缺少 langchain_openai，未在旧环境获得通过结果。
- 新增回归覆盖：robin 在任务额度耗尽时可创建任务，普通账号仍受限，空配置关闭豁免，以及豁免请求不消耗共享模型预算。
- 经用户明确允许，重启日常 Java／Python，Java 绑定 127.0.0.1:8080、Python 绑定 127.0.0.1:8001；启动环境显式设置 QUOTA_EXEMPT_USERNAME=robin。前端未重启。
- Java OpenAPI HTTP 200，Python health HTTP 200；只读确认日常库存在 username=robin、status=1。
- 未修改数据库和历史记录。未登录 robin 发起真实模型问答，未进行付费模型调用或公网部署验证。
- 运行日志：`.cache/robin-quota-runtime-1792743902671533000/`；测试日志：`/tmp/robin-quota-java.log`、`/tmp/robin-quota-python.log`。
