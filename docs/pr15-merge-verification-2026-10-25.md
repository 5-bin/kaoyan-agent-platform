# PR #15 合并兼容与隔离验证

日期：2026-10-25。分支`feat/question-import-tutor`，功能提交`9659f7b`，合并目标`upstream/main`的`33c20e1`。本文记录冲突解决后的工作树验证；记录完成时尚未创建合并提交、推送、执行业务数据库迁移或部署。

## 合并后的行为

- 保留管理员JSON批量预览、整批送审、来源登记及重复检查；题目仍须审核通过后才能进入学生题池。
- 保留上游新建批次固定题目快照及按快照判分；答题响应继续返回recordId，用于指定已判错的本人历史作答。辅导不使用现行题表替代旧快照，不改变判分。
- `/tasks`保持上游连续聊天与隐私界面；`/tasks/history`查看任务并继续错题追问。公开TaskView增加可空tutoring白名单，仅展示recordId、query、parentTaskId和最多六条role/content；不恢复公开userId或inputPayload。
- Java构造错题上下文，新生成历史消息标记wrong范围；Python必须同时验证模型启用、用户同意、供应商身份及wrong类别授权。缺少授权不发模型请求，返回原解析和提示；仅已授权范围的历史可以外发，模型载荷移除业务id和recordId。
- 保留上游LangChain、流式聊天、来源策略、预算、停止／清除与30天内容清理。默认思考参数仅为官方api.deepseek.com上的deepseek-flash自动关闭，显式enabled／disabled优先。
- 错题结果显示AI解释、原题解析或AI降级；解释内容按纯文本转义。普通任务继续采用上游Markdown与引用展示，不重新显示内部任务编号。

业务契约集中于[搭建文档7.4.1](../考研Agent平台搭建文档.md#741-错题解释与追问)，运行入口见[README](../README.md)。

## 实际检查

源码构建与浏览器测试在`.cache/pr15-merge-check`隔离副本运行；Python使用独立`.cache/pr15-venv`，未升级日常`.venv`。Java使用JDK17、内存H2、Redis替身及模型关闭的Python子进程。浏览器使用本机Chrome和随机测试端口／专用4173端口，无日常账号与浏览器状态。

| 检查 | 实际结果 | 范围与证据 |
| --- | --- | --- |
| Maven离线verify | 141项，0失败／错误／跳过，BUILD SUCCESS | `.cache/pr15-java.log`；包含实际Java→Python及错题任务持久化、白名单、归属、父轮次边界 |
| Python pytest | 241 passed | `.cache/pr15-python.log`；包含拒绝未授权／错误供应商／缺少wrong范围、过滤历史与模型ID、SDK本地传输校验；未联系供应商 |
| 前端生产构建 | 通过 | `.cache/pr15-frontend.log`；Vue／TypeScript及Vite，现有大包提示保留 |
| 桌面与手机浏览器 | 首轮160/162通过；修复后定向18/18通过 | `.cache/pr15-browser.log`及`pr15-browser-recheck.log`；两项失败为错题模式标签遗漏，补回标签并验证历史继续追问、原文转义、原解析／失败重试与普通聊天展示 |
| 真实HTTP／浏览器回归 | 15项通过 | 隔离副本`.cache/pr15-http.json`及外层`.cache/pr15-http.log`；真实Java／Python，H2，模型与Redis替身 |
| 录题管理浏览器 | 10项通过 | 隔离副本`.cache/pr15-admin.json`；真实Java与H2，桌面／手机管理流程 |
| 连续聊天浏览器链路 | 11项通过 | 隔离副本`.cache/pr15-chat.json`；受控SDK流、隔离持久库，含Java重启恢复 |
| 学情／隐私浏览器链路 | 17项通过 | 隔离副本`.cache/pr15-learning.json`；真实Java／Python，隐私授权及受控操作 |
| 项目／框架静态检查 | 通过 | `scripts/check-project.py`与`check-framework.py` |
| 脚本unittest | 8项通过 | UTF-8模式，`python -X utf8 -m unittest discover -s scripts/tests -v` |

初始Python隔离环境因复用依赖路径未加载pywin32启动路径，Qdrant锁失败；在独立环境安装该依赖后恢复。旧SDK测试的token字段断言按LangChain升级后的max_completion_tokens核对，并增加显式思考模式覆盖。题目索引的磁盘隐私检查改为关闭客户端后扫描全部文件，避免Windows独占锁阻止读取，不跳过隐私断言。Windows测试使用PYTHONUTF8=1。

Maven离线dependency插件前缀未缓存，无法生成classpath；隔离HTTP脚本使用本次成功Surefire运行记录中的实际java.class.path，没有更改依赖或使用日常JAR。

## 未运行与部署边界

- `scripts/feature-test.py`默认预览及额外pytest脚本集中的一个真实数据用例依赖Linux/macOS的fcntl，Windows无法运行。尝试WSL预览时该环境又缺少httpx，未继续安装或执行数据工具。额外脚本pytest为12通过、1项因fcntl未运行成功；这不计为全套通过。Linux CI仍须在推送后确认。
- 未运行真实MySQL迁移、日常题库导入、真实DeepSeek请求、模型效果评估或公网部署。H2和受控模型检查不代表真实供应商及MySQL验收。
- 批量导入／错题辅导本身无新迁移；上游连续聊天／个人文档／隐私已引入V10、V11、V12。部署负责人须核对现有V7—V9和V10—V12记录，仅受控执行缺失项，不能重跑含DROP语句的V1。Java与Python须按同一合并版本更新，新Python依赖应在独立环境安装验证。
- 本地代码和数据不会自动同步线上。PR检查通过并获审查批准后，由有权限的组员合并与部署；真实题库由管理员通过线上审核流程导入，密钥留在服务器安全配置。
- 既有`backend/`及旧验证输出目录未加入提交，日常MySQL、Redis、Java8080、Python8001和前端5173未由本轮检查停止或重启。
