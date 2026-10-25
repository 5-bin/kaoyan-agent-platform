# 检索质量与引用支持度验证（2026-10-24）

本轮面向课程／毕设演示，只优化“回答是否有依据、检索是否可解释”，不扩展刷题闭环或管理员发布流程。改动集中在Python Agent与结果展示；Java仅透传新增结果字段，旧客户端忽略即可。

## 范围与环境

- 语料：根`.env`的`RAG_DATA`，即`kaoyan-agent/knowledge/feature-2027-corpus.json`（4段408摘要 + 10校15专业）。
- 后端：`lexical`（默认）、`bm25`、`hybrid`；`hybrid`在本机没有向量就绪标记时按设计回退BM25，因此本轮**未验证真实向量融合质量**。
- 模型：根`.env`已启用`LLM_ENABLED`与DeepSeek兼容端点；只对4个知识问答执行真实请求，未对院校解释调用模型。
- 运行环境：项目`.cache/chat-venv`（已安装LangChain/OpenAI 2.x依赖），Python 3.13；未启动Java、MySQL、Redis、前端或公网服务。

## 改动

| 文件 | 变更 |
| --- | --- |
| [grounding.py](../kaoyan-agent/grounding.py) | 词项级引用支持度校验：claim级/句级、数字一致性、未知来源、免责句跳过、逐条`items`与聚合状态 |
| [retrieval.py](../kaoyan-agent/retrieval.py) | 新增字符n-gram BM25、`bm25`/`hybrid`后端、科目提示、按资料文档去重；hybrid无向量时回退 |
| [workflows.py](../kaoyan-agent/workflows.py) | 知识问答接入科目过滤与回退；claims逐条绑定来源；模型回答`UNSUPPORTED`时降级为来源摘要；院校解释逐候选核对 |
| [schemas.py](../kaoyan-agent/schemas.py) | `Answer`新增可选`claims[{text, sourceIds}]`，最多10条 |
| [prompts/zhishi_wenda.txt](../kaoyan-agent/prompts/zhishi_wenda.txt) | 要求按结论顺序输出claims，每条只能引用直接支持该结论的资料 |
| [config.py](../kaoyan-agent/config.py) | `RAG_BACKEND`增加`bm25`、`hybrid` |
| [tests/test_quality.py](../kaoyan-agent/tests/test_quality.py) | 14项检索、科目、claim级grounding、降级与回退测试 |
| [scripts/eval-quality.py](../scripts/eval-quality.py) | 冻结案例评测脚本；默认离线，`--model`才发真实请求；报告拒绝覆盖 |
| [scripts/fixtures/quality-cases.json](../scripts/fixtures/quality-cases.json) | 10个检索／终态／候选／澄清案例 |
| [TaskResultView.vue](../kaoyan-frontend/src/components/TaskResultView.vue) | 展示引用状态、支持比例，以及逐条结论/来源（S1—Sn、已核实/未核实） |
| [types/api.ts](../kaoyan-frontend/src/types/api.ts) | 新增可选`CitationSupport`及其`items`类型 |

## 结果

### 离线（模型关闭）

| 后端 | 通过 | 终态准确率 | 引用命中率 | 候选命中率 | 引用核对 |
| --- | --- | --- | --- | --- | --- |
| `lexical` | 10/10 | 1.0 | 1.0 | 1.0 | 未调用模型 |
| `bm25` | 10/10 | 1.0 | 1.0 | 1.0 | 未调用模型 |
| `hybrid`（回退BM25） | 10/10 | 1.0 | 1.0 | 1.0 | 未调用模型 |

覆盖：栈/队列、进程/线程、TCP可靠传输、主存/虚拟内存、两个未覆盖问题、2027学硕候选、缺年份追问、错误年份无候选、模糊CHAT追问。

发现并修复：BM25初版把单字“次/手”等计入查询，导致“三次握手”误命中存储层次与栈队列资料；改为多字查询必须命中二元词或ASCII词后恢复`UNSUPPORTED`。单字查询（如“栈”）仍保留单字召回。

### 真实模型（4个知识问答，lexical后端）

| 指标 | 结果 |
| --- | --- |
| 终态 | 4/4 `COMPLETED` |
| 引用命中 | 4/4 |
| 模型claims | 14条（各例4/3/4/3） |
| 引用核对 | 14/14 条claim通过支持度核对 |
| 支持状态 | 4/4 `SUPPORTED` |
| 说明 | 每例一次主模型调用；未使用plan/stream会话入口 |

首轮4例中有一句“资料未进一步说明……”被词项校验计为低支持，说明免责/范围说明句会误报；已在`grounding.py`跳过此类句子并重跑，结果为14/14。该调整不改变事实性结论的判定阈值。

模型返回claims后，每条只与自己的`sourceIds`对应原文核对；示例中TCP一例的claim支持比分别为0.783、0.957、1.0，均高于0.34阈值。另做一次单例真实请求“TCP三次握手和四次挥手的过程”，模型明确说明资料未覆盖、未编造步骤，claims仅复述原文已覆盖内容并通过核对；该单例未写入报告文件。

报告文件（本地`.cache`，不提交）：`quality-report-offline-20261024.json`、`quality-report-offline-claims-20261024.json`、`quality-report-bm25b-20261024.json`、`quality-report-hybridb-20261024.json`、`quality-report-claims-20261024.json`。

## 未验证与限制

- 引用支持度是词项重叠基线，**不能识别否定、同义改写和自相矛盾**；“线程拥有完全相同的执行状态”这类与原文相反但复用词汇的句子仍可能通过。
- 只验证了4个知识问答的真实模型链路；院校AI解释、对话plan/stream、学情分析、笔记建议均未调用真实模型。
- `hybrid`只验证了“无向量标记时回退BM25”，未验证Qdrant命中与RRF排序效果。
- 10个案例是演示级冻结集，不是搭建文档要求的30例领域评估；没有人工评分、A/B或同模型对比。
- 前端生产构建已通过（Vite 3.57s，仍有大体积资源块提示），结果页会展示引用状态、支持比例和逐条结论/来源；未运行浏览器端到端检查。
- 未运行Java `mvnw verify`、MySQL/Redis联调、SSE浏览器链路；Java仅透传新增结果字段，未改判分或业务规则。
- claim文本由模型生成，可能与answer措辞不完全一致；claim数量、粒度也不稳定。`claims`缺失时自动回退句级核对，旧结果不受影响。
- 结果只说明本机、本语料、本模型配置下的表现，不代表全国院校覆盖或正式领域验收。

## 复现

```bash
# 从项目根目录
.cache/chat-venv/bin/python scripts/eval-quality.py \
  --output .cache/quality-report-offline-$(date +%Y%m%d).json

.cache/chat-venv/bin/python scripts/eval-quality.py --backend bm25 \
  --output .cache/quality-report-bm25-$(date +%Y%m%d).json

# 会产生真实供应商请求与费用；先用 --only/--limit 控制数量
.cache/chat-venv/bin/python scripts/eval-quality.py --model \
  --only qa-stack,qa-thread,qa-tcp,qa-memory \
  --output .cache/quality-report-model-$(date +%Y%m%d).json
```

Python回归：`.cache/chat-venv/bin/python -m pytest -q kaoyan-agent/tests`，本轮178项通过、1项真实Qdrant测试按既有条件排除。前端生产构建：`npm run build`通过。Java `mvnw verify`未运行。
