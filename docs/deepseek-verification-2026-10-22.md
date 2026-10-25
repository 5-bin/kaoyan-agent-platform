# DeepSeek真实模型接入验证

日期：2026-10-22。项目：kaoyan-agent-platform-adaptation。

## 环境与方法

使用本机`.cache/chat-venv`、根`.env`的DeepSeek官方API配置、`deepseek-flash`路由与主模型、`LLM_THINKING_MODE=disabled`、默认词项检索。配置检查只输出是否已填写，不输出密钥。资料版本为`rag-v1-650e0ac88cdf5f0c`，沿用现有20秒单次模型超时和42秒工作流超时。

以httpx ASGITransport在进程内调用实际FastAPI `/internal/rag/conversation/stream`，经过内部认证、LangChain上下文解析、检索、真实供应商调用和结果校验。第二轮传入首轮问题与已校验答案，使用合成测试上下文；不读取个人档案或写入业务数据库。

| 检查 | 结果 |
| --- | --- |
| 首问“请解释进程与线程的区别。” | 2.51秒；COMPLETED；explanationMode=ai；80个delta事件 |
| 追问“它们共享哪些资源，哪些资源是各自独立的？” | 2.07秒；COMPLETED；explanationMode=ai；77个delta事件 |
| 上下文解析 | 第二轮改写为“同一进程内的多个线程共享哪些资源，哪些资源是各自独立的？” |
| 引用与内容核对 | 两轮引用均为os-threads#0；共享地址空间、各自保留程序计数器／寄存器状态／栈，与本轮本地检索摘要一致 |
| 未覆盖信息 | 回答明确说明摘要未进一步覆盖的资源类别，没有将其补造为本轮证据 |

原始结果保存在本机忽略目录`.cache/deepseek-real-20261022-1792677561020014000.json`，仅包含合成问题、回答、来源编号及检查指标，不包含凭证。耗时为整轮请求耗时，未采集供应商token用量和实际账单。ASGITransport缓冲响应，本轮验证收到模型增量事件，不据此证明浏览器首字延迟或网络实时到达顺序。

## 整站就绪检查与待确认操作

MySQL 3306和Redis 6379正在监听；前端5173、Python8001、Java8080／8081未监听。使用环境中的数据库配置，只读检查information_schema，确认task.deleted_at存在，但chat_conversation、chat_message、chat_generation、personal_document、personal_document_version均缺失。

整站启动前需要确认后备份日常数据库，依次应用V10／V11增量建表脚本，再使用新版依赖和构建启动Python、Java及前端。脚本只新增上述5张表，不执行V1、不清空旧账号或任务。MySQL的多条DDL不构成一个可整体回滚的事务；部分失败时应先核对已建表结构，不能整份盲目重跑。回退旧代码可保留新增表；恢复数据应依据备份另行执行。

本轮未执行日常数据库迁移、服务启停、账号写入或浏览器操作；未验证Java会话持久化、停止／重试、文档保存和整站真实供应商链路。Python回归85项通过属于本次配置支持改动的先前验证，真实供应商结果以本记录两轮为限。
