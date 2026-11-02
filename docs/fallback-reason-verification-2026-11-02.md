# 对话澄清续接、数字校验与AI降级原因验证记录（2026-11-02）

## 起因

用户反馈：择校对话中系统追问“学硕或专硕”后，回答“学硕”得到泛化澄清和无关的 TCP 例句；同一轮学情分析显示“AI分析不可用”；回答里同一知识点先后出现“16次”和“8次”。本轮未取得该次会话的原始请求与日志，以下原因由代码阅读和离线复现得出，未用真实记录核对。

## 原因与修改

| 问题 | 原因 | 修改 |
| --- | --- | --- |
| 回答“学硕”后答非所问 | 本地规则已能识别“学硕”，但允许模型时先交给模型解析，模型的泛化澄清被直接采用；Java 传给下一轮的历史只有上一轮 `answer` 正文，不含 `followUp` 里的追问 | 纯条件补充直接按本地规则合并（[会话说明](conversations.md)第三批修订）；Java 在助手历史后附“待补充：…” |
| “AI分析不可用” | 数字校验按子串匹配，正确率换算为百分数（27.9%）会被拒，“61”又会让“1”“6”误通过；提示词要求模型自行相减，算出的错误次数同样被拒 | 按完整数值比对并允许比值的四舍五入百分数（[RAG契约](rag.md)）；代码补充 `wrongAttempts`，提示词不再要求相减 |
| “16次”与“8次” | 区间作答次数（含同题重复）与画像独立样本（全部历史、同题7天计1次、不含提示辅助、按难度分组）口径不同，回答未注明 | 规则回答与提示词分别注明口径（[学情契约](assistant-learning-contract.md)） |
| 页面无法区分降级原因 | 所有模型失败共用一句提示 | 新增可选 `fallbackReason`（[搭建文档契约](../考研Agent平台搭建文档.md#ai降级原因增量契约2026-11-02)）；Python 映射固定码，Java 校验，前端在提示后附原因；日志追加 `reason=` 原因码 |

核对后无需修改：导出 `ExportSources.java` 第117行读取的练习总结 `accuracy` 已是百分数，统计表第187行读取比值并乘100，两处口径各自正确。

## 实际运行的验证

环境：本机 macOS；Python 使用 `.cache/mcp-pdf-venv`（根目录 `.venv` 缺 `hello_agents`，`.cache/helloagents-venv` 缺 `mcp`）；Java 测试设置 `PYTHON_EXECUTABLE` 为该环境，`mvnw` 无执行权限，使用 `bash mvnw`。

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| Python 全量 | `cd kaoyan-agent && ../.cache/mcp-pdf-venv/bin/python -m pytest -q` | 842 passed |
| Java 全量 | `cd kaoyan-B && bash mvnw -B -ntp verify` | 223 项，0 失败，2 项跳过（`ExportIntegrationTest`），BUILD SUCCESS |
| 前端生产构建 | `cd kaoyan-frontend && npm run build` | 通过（含 `vue-tsc` 类型检查） |

新增测试：`kaoyan-agent/tests/test_condition_supplement.py`、`kaoyan-agent/tests/test_fallback_reason.py`；`kaoyan-agent/tests/test_refactor_baseline.py` 按日期覆盖 `learning_True`、`qa_failure`、`schools_ai` 的预期，冻结数据本身不动；Java 在 `ConversationPlanValidationTest`、`TaskServiceImplTest` 中补充历史追问及原因码校验。

同一时间工作区内另有并行修改（院校库、招生指标等），上述全量结果包含这些修改，测试数量不能单独归因于本轮。

## 未运行

- 真实模型回放：提示词修改后模型是否按口径表述、是否使用 `wrongAttempts` 未验证。
- Playwright 浏览器回归及页面实际显示原因文案：未运行（需启动预览服务）。
- 隔离 MySQL、Redis 与三端联调：未运行。
- 未重启日常服务、未部署；需加载新版 Java、Python 和前端后生效。
