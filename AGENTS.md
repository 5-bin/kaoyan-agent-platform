# 开发约定

- 当前架构与接口以 README.md 和 docs/rag.md 为准。docs/work*.md 与 docs/agent.md 是历史生成提示词，不按其内容重新生成现有工程。
- 前端 kaoyan-frontend 只访问 Java /api；Java kaoyan-B 管认证、账号归属、业务库和任务保存；Python kaoyan-agent 只读静态副本及检索库，不直连业务库。
- 明确任务不经模型猜测类型；只有 CHAT 自动识别。推荐硬条件与判分由代码决定，AI只在已知资料和候选内解释。
- 修改契约同时核对 Java DTO、Python schema、前端类型/展示及测试。保留旧记录，以只读旧格式显示，不把旧占位结果当成核验推荐。
- 凭证只放根 .env 或环境变量；不提交业务库、索引、权重、.venv、node_modules、target、截图与测试原始日志。历史硬编码值不得复用。
- 资料带官方出处、定位、版本、核验日期及许可说明。变更资料必须重新导入索引，历史集合与资料留存以便回滚。未覆盖时追问或明确未覆盖，不生成招生事实。
- 涉及作答快照的新版本需要显式执行V7迁移；不要对已有库执行含DROP的V1或演示种子来解决问题。
- Python测试：根虚拟环境 python -m pytest -q kaoyan-agent/tests。Java：kaoyan-B中运行mvnw verify，PYTHON_EXECUTABLE指向同一虚拟环境；测试只使用隔离H2和临时Python子进程。
- 前端运行npm run build与npm run test:e2e；浏览器使用隔离上下文，不读取个人浏览器资料。模型测试默认模拟，真实调用和外部部署按用户授权范围执行。
- 说明实际验证范围，不把本机通过写成远端CI、公网、真实MySQL或付费供应商验收通过。保留其他成员修改，PR说明接口变化、数据迁移与测试证据。
