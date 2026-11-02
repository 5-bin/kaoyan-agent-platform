# P2 审核修复验证记录（2026-11-02）

## 范围

代码审核提出的 4 个 P2 问题，均在代码中核实后修复。用户确认：每日学习时长上限 12 小时；复合招生请求提示拆分，不新增编排契约。

| 问题 | 原因 | 修改 |
| --- | --- | --- |
| 复习计划只校验格式与天数 | 用户声明的每日时长原样采用；模型计划中的时长、目标分、统计次数不核对；降级未写 `fallbackReason` | `agents/study.py` 新增 12 小时上限与 `check_study_plan`，不符时回退规则计划并附原因码；提示词 `prompts/study_planner.txt` 补充约束 |
| 招生查询吞掉同句其他事项 | Java `SchoolCatalogService.plan` 与 Python `local_orchestration` 均先返回单一招生计划 | Python `ADMISSION_COMPOUND`／Java `AdmissionLinksValidator.COMPOUND` 逐字一致，命中时返回拆分澄清，不带查询或链接参数 |
| 学科误判（“TCP协议栈”判为数据结构） | `detect_subject` 按顺序取第一个子串匹配 | `retrieval.subject_terms`：明确科目名优先，不重叠长词优先，ASCII 整词匹配，跨科目不指定；`agents/knowledge.py` 丢弃不提及主题词的弱匹配结果，放宽后仍无则 `UNSUPPORTED` |
| 服务可能在请求中下载权重 | `main.py` 用默认 `local_files_only=False`；fastembed 缺缓存抛 `ValueError`，混合检索不捕获 | 服务端 `Retriever(..., local_files_only=True)`；`FastEmbedEncoder` 在只读模式把 `ValueError` 转为 `ToolUnavailable`，混合检索回退 BM25 |

契约与说明：[搭建文档](../考研Agent平台搭建文档.md)（院校库查询、招生官网网址、统一规划三处补充）、[会话说明](conversations.md)第四批修订、[RAG契约](rag.md)、README 向量模式一段。

现有测试调整：`tests/test_quality.py` 中“主存和虚拟内存”的预期由“计算机组成原理”改为 `None`（跨两个科目，不再取列表中第一个），并补充“TCP协议栈”用例；`tests/test_mcp_knowledge.py` 改为 patch `subject_terms`。

## 实际运行的验证

环境同[上一份记录](fallback-reason-verification-2026-11-02.md)：Python 使用 `.cache/mcp-pdf-venv`，Java 使用 `bash mvnw` 并设置 `PYTHON_EXECUTABLE`。

| 检查 | 结果 |
| --- | --- |
| `kaoyan-agent/tests/test_review_p2.py`（新增，含参数化共 32 项） | 32 passed |
| Python 全量 `pytest -q` | 908 passed |
| Java `AdmissionCompoundTest`（新增，与 Python 共用同一组复合／单一用例） | 通过 |
| Java 全量 `bash mvnw -B -ntp verify` | 225 项，0 失败，2 项跳过（`ExportIntegrationTest`），BUILD SUCCESS |

“权重缺失时回退”的测试用替身让 fastembed 加载失败，并在临时目录建立就绪标记，没有真实删除或下载权重。

同一时间工作区内另有并行修改，全量测试数量包含那些修改，不能单独归因于本轮。

## 未运行

- 真实模型：提示词补充后的复习计划是否遵守时长与数字约束未验证。
- 使用真实学习资料语料的检索回放（审核中“TCP协议栈”返回栈与二分查找的案例）：未运行，本轮只用仓库演示语料和替身验证。
- 浏览器回归、三端联调、日常服务重启：未运行；需要重新加载新版 Java 和 Python 才能生效。
