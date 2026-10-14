> 历史生成提示词，保留原始内容。当前运行入口、接口适配和验证状态见 [README](../README.md) 与 [当前框架适配](当前框架适配.md)；以下步骤不表示已经执行，配置与凭证示例不直接用于部署。

# 考研 Agent 服务 - 豆包分阶段提示词

> 使用说明：按阶段 0 → 4 依次执行。
> 每阶段完成后手动测试，确认无误再进下一阶段。
> 每阶段结束 `git commit` 存档。
> 阶段 0-2 是必须的，阶段 3-4 是优化项，可以先跳过。
> Python 版本：3.12（推荐）；3.13 可用但部分依赖仍在适配。

---

## 阶段 0：初始化

### 命令
```bash
mkdir kaoyan-agent && cd kaoyan-agent
```

### 提示词
```
读取当前目录的 AGENTS.md，确认技术栈和规范。
然后创建以下基础文件：
1. requirements.txt
2. .env.example
3. .gitignore
4. sql/init.sql（内容从 AGENTS.md 的"数据库表（只读）"章节完整复制）

requirements.txt 内容：
fastapi==0.115.6
uvicorn[standard]==0.32.1
pydantic==2.10.3
pydantic-settings==2.7.0
openai==1.57.4
python-dotenv==1.0.1
httpx==0.28.1
sqlalchemy==2.0.36
aiomysql==0.2.0

.env.example 内容：
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL_ROUTER=glm-4-flash
LLM_MODEL_MAIN=glm-4-plus
AGENT_INTERNAL_KEY=kaoyan-agent-internal-key-2026
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=kaoyan
DB_USER=root
DB_PASSWORD=your_password
LOG_LEVEL=INFO

.gitignore 内容：
.env
__pycache__/
*.pyc
.venv/
venv/
.pytest_cache/

sql/init.sql 内容：
从 AGENTS.md 的"数据库表（只读）"章节中的 SQL 代码块完整复制。
包含建库、建 question 表、5 道种子数据。

先输出文件清单，我确认后再逐个生成。
不要创建其他文件。

注意：用户环境有 Python 3.12 和 3.13，统一使用 3.12。
sql/init.sql 生成后，用户会手动执行这个脚本建库建表。
```

### 执行 SQL

用户在开始写代码前，先手动执行 `sql/init.sql`：

```bash
mysql -u root -p < sql/init.sql
```

验证：
```sql
USE kaoyan;
SHOW TABLES;               -- 应看到 question 表
SELECT COUNT(*) FROM question;  -- 应返回 5
```

---

## 阶段 1：最小可跑通骨架

### 提示词
```
# 任务
创建 FastAPI 骨架，实现 /internal/rag/chat 接口，
先不接 LLM 和数据库，返回固定结构，确保 Spring 端能调通。

# 上下文
参考 AGENTS.md 的接口契约和目录结构。
Python 版本 3.12。
sql/init.sql 已由用户手动执行，question 表已存在。

# 需要生成的文件

## 1. config.py
- 用 pydantic-settings 的 BaseSettings
- 读取：LLM_API_KEY、LLM_BASE_URL、LLM_MODEL_ROUTER、
  LLM_MODEL_MAIN、AGENT_INTERNAL_KEY、DB_HOST、DB_PORT、
  DB_NAME、DB_USER、DB_PASSWORD、LOG_LEVEL
- 启动时校验 AGENT_INTERNAL_KEY 至少 16 位 ASCII，否则抛异常
- 导出 settings 单例

## 2. schemas.py
- ChatRequest：taskId、userId、taskType、userInput（Optional）、
  sessionId（Optional）、correctQuestionIds、wrongQuestionIds、
  messages、profile
- ChatResponse：taskId、status、result、references、errorMessage
- 用 Pydantic BaseModel，字段加中文 description

## 3. main.py
- 创建 FastAPI app，title="考研 Agent 服务"
- POST /internal/rag/chat
- 从 Header 读 X-Internal-Key，与 config 比对，不匹配返回 401
- 校验 taskId 非空，否则返回 FAILED
- 先返回固定结构：
  {
    "taskId": req.taskId,
    "status": "SUCCESS",
    "result": {
      "answer": f"收到任务：{req.taskType}（骨架已通）"
    },
    "references": [],
    "errorMessage": null
  }
- 配置 logging，级别从 config 读
- 加 GET /health 返回 {"status": "ok"}

## 4. 启动脚本说明
写进 main.py 顶部注释：
python3.12 -m venv .venv
source .venv/bin/activate
# Windows: py -3.12 -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填 AGENT_INTERNAL_KEY、DB_PASSWORD、LLM_API_KEY
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# 约束
- 严格按 AGENTS.md
- 不引入未列出的依赖
- Python 3.12
- 先输出文件清单，我确认后再逐个生成
- 不要创建 db.py、repository.py、handlers、prompts 目录（下一阶段再建）

# 验证
curl -X POST http://localhost:8001/internal/rag/chat \
  -H "X-Internal-Key: kaoyan-agent-internal-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"taskId":"test-1","userId":2,"taskType":"KNOWLEDGE_QA","userInput":"测试","messages":[]}'
应返回固定结构。
```

---

## 阶段 2：接 LLM + 数据库 + 意图路由 + 四类场景

### 提示词
```
# 任务
接入 LLM 和 MySQL，实现意图路由、批次总结、知识问答、院校推荐、闲聊。
提示词从 prompts/ 目录读取，不硬编码。

# 上下文
阶段 1 骨架已就绪。参考 AGENTS.md。
Python 独立连接 MySQL，只读 question 表，用 SQLAlchemy async + aiomysql。
Python 版本 3.12。
question 表已由 sql/init.sql 建立，包含 5 道种子数据。

# 需要生成的文件

## 1. db.py
- 用 SQLAlchemy 2.0 的 create_async_engine
- 连接串：mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}
- pool_size=5, max_overflow=5, pool_pre_ping=True, echo=False
- 导出 SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
- 提供 get_session 依赖函数

## 2. repository.py
- async def get_questions_by_ids(question_ids: list[int]) -> list[dict]
  - 用 text() 写原生 SQL
  - SELECT id, subject, knowledge_point, content, option_a, option_b,
    option_c, option_d, answer, analysis, difficulty, question_type
    FROM question WHERE id IN :ids AND active = 1
  - 返回 list[dict]
  - 空列表直接返回 []
- 只 SELECT，不写

## 3. prompts/ 目录下 5 个文件

### prompts/intent_router.txt
你是一个意图分类器。根据用户输入和对话历史，判断属于以下哪一类：

- TUIJIAN_YUANXIAO：考研院校推荐。用户询问报考哪所学校、专业选择、分数线对比。
- ZHISHI_WENDA：408 知识问答。用户问数据结构、操作系统、计算机网络、计算机组成原理的概念。
- CHANGUI：闲聊或无法归类。

规则：
1. 如果用户提到院校名、专业、分数线、报录比、择校，判为 TUIJIAN_YUANXIAO。
2. 如果用户只问概念、原理、算法，判为 ZHISHI_WENDA。
3. 不确定时判为 CHANGUI。

注意：批次总结 PRACTICE_SUMMARY 不走意图路由，由 taskType 直接判定。

只输出 JSON，不要任何解释：
{
  "intent": "TUIJIAN_YUANXIAO | ZHISHI_WENDA | CHANGUI",
  "subject": "数据结构 | 操作系统 | 计算机网络 | 计算机组成原理 | null",
  "confidence": 0.0 到 1.0
}

### prompts/practice_summary.txt
你是一位计算机考研 408 辅导老师，有 10 年教学经验。
学生刚做完一批练习题，你需要给出整体总结和针对性建议。

## 本次练习数据
- 总题数：{total}
- 答对：{correct_count}
- 正确率：{accuracy}%
- 学生档案：目标院校 {target_school}，目标专业 {target_major}，背景 {background}

## 答对的题目
{correct_list}

## 答错的题目
{wrong_list}

## 总结要求
1. 先整体评价本次表现，语气鼓励为主
2. 分析错误集中在哪些知识点，找出薄弱环节
3. 针对错题，讲解正确思路（每题 50-100 字）
4. 给出下一步复习建议，结合学生的目标院校
5. 如果答对率很高，指出可以挑战的进阶方向
6. 不要逐题复述解析，要抓重点

## 输出格式（严格 JSON）
{
  "summary": "整体评价，100-200 字",
  "accuracy_comment": "对正确率的评价",
  "weak_points": [
    {
      "knowledge_point": "薄弱知识点",
      "related_question_ids": [2, 4],
      "suggestion": "针对性建议"
    }
  ],
  "wrong_analysis": [
    {
      "question_id": 2,
      "brief": "错误原因简要分析，50-100 字"
    }
  ],
  "next_steps": "下一步复习建议，100-200 字",
  "references": []
}

### prompts/tuijian_yuanxiao.txt
你是一位考研择校规划师，熟悉全国计算机相关院校的招生情况。

## 任务
根据学生的背景和需求，推荐合适的考研院校。

## 输入
- 学生档案：
  - 目标专业：{target_major}
  - 考试年份：{exam_year}
  - 本科背景：{background}
  - 当前目标院校：{target_school}
- 学生提问：{user_input}
- 院校数据：{rag_context}

## 推荐原则
1. 分三档推荐：冲刺、稳妥、保底，每档 2-3 所
2. 结合学生背景，不要脱离实际推荐顶尖院校
3. 每所院校说明推荐理由：分数线、报录比、专业课难度、地域
4. 如果资料中没有某校数据，不要编造，明确说明"暂无数据"
5. 提醒学生关注招生简章变化

## 输出要求
- 用中文回答
- 客观中立，不吹捧也不贬低任何院校
- 引用资料时标注 [资料1]

## 输出格式（严格 JSON）
{
  "summary": "一句话总结推荐思路",
  "rush": [
    {
      "school": "院校名",
      "major": "专业名",
      "reason": "推荐理由",
      "score_line": "参考分数线",
      "risk": "风险提示"
    }
  ],
  "stable": [],
  "safe": [],
  "tips": "择校建议，100-200 字",
  "references": ["资料1"]
}

### prompts/zhishi_wenda.txt
你是一位计算机考研 408 答疑老师。

## 任务
回答学生关于 408 四科（数据结构、操作系统、计算机网络、计算机组成原理）的概念性问题。

## 输入
- 学生问题：{user_input}
- 对话历史：{messages}
- 参考资料：{rag_context}

## 回答原则
1. 先给结论，再展开解释
2. 涉及概念对比时，用表格或分点
3. 能举例子就举例子，尤其是数据结构和算法
4. 参考资料里有相关内容时优先使用，标注 [资料1]
5. 资料里没有的，用你自己的知识回答，但不要编造具体数字
6. 如果问题超出 408 范围，礼貌说明并给出相关方向

## 输出格式（严格 JSON）
{
  "answer": "完整回答，300-800 字",
  "key_points": ["要点1", "要点2", "要点3"],
  "example": "举例说明（可选，没有则空字符串）",
  "related": ["相关知识点1", "相关知识点2"],
  "references": ["资料1"]
}

### prompts/rag_template.txt
## 参考资料

[资料1]
标题：{title}
来源：{source}
内容：{content}

[资料2]
标题：{title}
来源：{source}
内容：{content}

（最多 5 条，按相关度排序）

## 4. prompts.py
- 用 pathlib.Path(__file__).parent / "prompts" 定位目录
- 启动时一次性加载所有 .txt 到内存 dict
- 提供 get(name: str) -> str
- 文件不存在抛 FileNotFoundError

## 5. llm_client.py
- 用 openai.AsyncOpenAI
- base_url 和 api_key 从 config 读
- async def chat(model: str, system: str, user: str) -> dict
  - 调用 chat.completions.create
  - response_format={"type": "json_object"}
  - temperature=0.3
  - timeout=30
  - 返回解析后的 dict
  - JSON 解析失败重试 1 次
  - 仍失败抛异常
- 暴露单例 llm_client

## 6. router.py
- async def route(user_input: str, messages: list) -> dict
- 读 prompts.get("intent_router") 作为 system
- user 传入 user_input
- 调 llm_client.chat(model=settings.LLM_MODEL_ROUTER, ...)
- 返回 {"intent", "subject", "confidence"}

## 7. handlers/ 目录

### handlers/__init__.py
空文件

### handlers/summary.py
import logging
from llm_client import llm_client
from prompts import prompts
from repository import get_questions_by_ids
from config import settings

logger = logging.getLogger(__name__)


async def handle(req) -> dict:
    """
    批次总结：拉题目详情，让 LLM 生成整批练习的点评
    """
    all_ids = req.correctQuestionIds + req.wrongQuestionIds
    if not all_ids:
        return {"summary": "本次练习没有可总结的内容。",
                "weak_points": [], "wrong_analysis": [],
                "next_steps": "", "references": []}

    questions = await get_questions_by_ids(all_ids)
    qmap = {q["id"]: q for q in questions}

    correct_list = _format_questions(
        [qmap[qid] for qid in req.correctQuestionIds if qid in qmap], "答对")
    wrong_list = _format_questions(
        [qmap[qid] for qid in req.wrongQuestionIds if qid in qmap], "答错")

    total = len(all_ids)
    correct_count = len(req.correctQuestionIds)
    accuracy = round(correct_count / total * 100, 1) if total else 0

    system = prompts.get("practice_summary").format(
        total=total,
        correct_count=correct_count,
        accuracy=accuracy,
        correct_list=correct_list or "（无）",
        wrong_list=wrong_list or "（无）",
        target_school=req.profile.get("targetSchool", "未填写"),
        target_major=req.profile.get("targetMajor", "未填写"),
        background=req.profile.get("background", "未填写"),
    )

    result = await llm_client.chat(
        model=settings.LLM_MODEL_MAIN,
        system=system,
        user="请生成本次练习的总结。",
    )
    return result


def _format_questions(questions: list[dict], tag: str) -> str:
    """把题目列表拼成文本"""
    lines = []
    for q in questions:
        lines.append(
            f"[{tag}] id={q['id']} 科目={q['subject']} "
            f"知识点={q.get('knowledge_point', '')}\n"
            f"题干：{q['content'][:200]}\n"
            f"正确答案：{q['answer']}\n"
            f"解析：{(q.get('analysis') or '')[:200]}\n"
        )
    return "\n".join(lines)

### handlers/wenda.py
- async def handle(user_input: str, profile: dict, messages: list) -> dict
- 读 prompts.get("zhishi_wenda")
- messages 拼成文本
- rag_context 填 "暂无参考资料"
- 调 llm_client.chat(model=settings.LLM_MODEL_MAIN, ...)

### handlers/tuijian.py
- async def handle(user_input: str, profile: dict, messages: list) -> dict
- 读 prompts.get("tuijian_yuanxiao")
- 把 profile 字段填进提示词
- rag_context 填 "暂无参考资料"
- 调 llm_client.chat(model=settings.LLM_MODEL_MAIN, ...)

### handlers/changui.py
- async def handle(user_input: str, profile: dict, messages: list) -> dict
- 不调 LLM，直接返回：
  {"answer": "这个问题我暂时答不了，可以问我 408 题目或考研择校。"}

## 8. main.py 改动
- 接口逻辑改成：
  1. 校验 X-Internal-Key
  2. 如果 taskType == "PRACTICE_SUMMARY"，直接调 summary.handle(req)
  3. 否则调 router.route(req.userInput, req.messages) 拿 intent
  4. 按 intent 分发到对应 handler
  5. 组装 ChatResponse 返回
- 任何异常都捕获，返回 status=FAILED，errorMessage 填异常信息
- 日志记录 taskId、intent、耗时，不打印完整 prompt

# 约束
- 严格按 AGENTS.md
- 提示词必须从文件读，不能硬编码
- LLM 调用和数据库操作用 async，不用同步
- 禁止写 question 表
- Python 3.12
- 先输出文件清单，我确认后再逐个生成

# 验证
1. 批次总结（question 表已有 id=1..5 的数据）：
curl -X POST http://localhost:8001/internal/rag/chat \
  -H "X-Internal-Key: kaoyan-agent-internal-key-2026" \
  -H "Content-Type: application/json" \
  -d '{
    "taskId":"t1","userId":2,"taskType":"PRACTICE_SUMMARY",
    "sessionId":"sess-1",
    "correctQuestionIds":[1,3,5],"wrongQuestionIds":[2,4],
    "messages":[],
    "profile":{"targetSchool":"清华大学","targetMajor":"计算机科学与技术","examYear":2026,"background":"本科计算机"}
  }'
应返回 summary、weak_points、wrong_analysis、next_steps

2. 知识问答：
curl -X POST http://localhost:8001/internal/rag/chat \
  -H "X-Internal-Key: kaoyan-agent-internal-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"taskId":"t2","userId":2,"taskType":"KNOWLEDGE_QA","userInput":"TCP 三次握手是什么？","messages":[]}'
应返回 intent=ZHISHI_WENDA 和真实回答

3. 院校推荐：
curl -X POST http://localhost:8001/internal/rag/chat \
  -H "X-Internal-Key: kaoyan-agent-internal-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"taskId":"t3","userId":2,"taskType":"SCHOOL_RECOMMEND","userInput":"我想考福建的计算机","messages":[],"profile":{"targetMajor":"计算机科学与技术","examYear":2026,"background":"本科计算机"}}'
应返回 intent=TUIJIAN_YUANXIAO 和推荐结果

4. 闲聊：
curl ... -d '{"taskId":"t4","userId":2,"taskType":"CHAT","userInput":"你好","messages":[]}'
应返回 intent=CHANGUI
```

---

## 阶段 3：接入向量库 + RAG（优化项，可跳过）

### 提示词
```
# 任务
接入向量库，实现 RAG 检索，替换 handlers 里的 "暂无参考资料"。

# 上下文
阶段 2 已完成。
参考 AGENTS.md。
Python 版本 3.12。

# 需要生成的文件

## 1. requirements.txt 追加
qdrant-client==1.12.1
sentence-transformers==3.3.1

## 2. config.py 追加
VECTOR_DB_URL、EMBEDDING_MODEL（默认 BAAI/bge-small-zh-v1.5）、
RAG_TOP_K（默认 5）、RAG_SCORE_THRESHOLD（默认 0.6）

## 3. retriever.py
- 初始化 Qdrant 客户端
- 初始化 sentence-transformers 模型
- async def retrieve(query: str, domain: str, top_k: int = 5) -> list[dict]
  - domain 取值 "408" 或 "school"
  - embed query
  - 向量检索 top_k
  - 过滤 score < threshold
  - 返回 [{"title", "source", "content"}]

## 4. rag_builder.py
- def build_context(docs: list[dict]) -> str
- 按 prompts/rag_template.txt 格式拼接
- 无文档返回 "暂无参考资料"
- 每条截断到 500 字

## 5. 更新 handlers
- wenda.py：调 retrieve(user_input, "408")
- tuijian.py：调 retrieve(user_input, "school")
- summary.py：不用 RAG

## 6. scripts/ingest.py
- 读取 data/408/*.md 和 data/schools/*.json
- 分块（按段落，每块 500 字）
- embed 后写入 Qdrant
- 支持增量更新（按 doc_id 去重）

## 7. data/ 目录
- 先放 1-2 个示例文件
- 格式说明写在 README

# 约束
- 向量库用 Qdrant（本地 Docker 起）
- Embedding 用本地模型，不调外部 API
- 检索失败不能影响主流程，降级为 "暂无参考资料"
- Python 3.12
- 先输出文件清单，我确认后再逐个生成
```

---

## 阶段 4：接入 RabbitMQ + Nacos（优化项，可跳过）

### 提示词
```
# 任务
接入 RabbitMQ 消费和 Nacos 注册。

# 上下文
阶段 3 已完成。
参考 AGENTS.md。
Python 版本 3.12。

# 需要生成的文件

## 1. requirements.txt 追加
aio-pika==9.4.3
nacos-sdk-python==0.1.12

## 2. config.py 追加
RABBITMQ_URL、RABBITMQ_QUEUE_DOC_SYNC（默认 "kaoyan.doc.sync"）、
NACOS_SERVER、NACOS_NAMESPACE、NACOS_SERVICE_NAME（默认 "kaoyan-agent"）、
NACOS_SERVICE_PORT（默认 8001）

## 3. mq_consumer.py
- 启动时连 RabbitMQ
- 消费 kaoyan.doc.sync 队列
- 消息体：{"docId": 123, "action": "UPSERT" | "DELETE", "payload": {...}}
- UPSERT：调 ingest 逻辑更新向量库
- DELETE：按 docId 删除向量
- 保证幂等：同一 docId 重复消息不重复插入
- 失败 nack 不 requeue（避免死循环）

## 4. nacos_register.py
- 启动时向 Nacos 注册服务
- 服务名 kaoyan-agent，端口 8001
- 优雅关闭时注销

## 5. 更新 main.py
- 用 FastAPI lifespan 管理 MQ 消费者和 Nacos 注册
- 启动顺序：Nacos 注册 → MQ 消费者 → FastAPI 就绪

# 约束
- MQ 消费和 Nacos 注册失败不能阻止 FastAPI 启动，只记录日志
- 用 async 方式
- Python 3.12
- 先输出文件清单，我确认后再逐个生成
```

---

## 附：豆包出错回滚策略

| 症状 | 处理 |
|---|---|
| 生成了多余的文件 | 删掉，重新给更严格的提示词 |
| 提示词硬编码在 .py 里 | 提示词强调"必须从 prompts/ 读" |
| 用同步方式调 LLM 或 DB | 提示词强调 `async def`、`AsyncOpenAI`、`create_async_engine` |
| LLM 返回不是 JSON | 提示词强调 `response_format={"type": "json_object"}` |
| 接口返回 HTTP 500 | 提示词强调"永远返回 200，业务失败用 status 字段" |
| 引入了未列出的依赖 | 提示词强调"禁止引入未列出的依赖" |
| 提示词文件路径写错 | 用 `Path(__file__).parent / "prompts"` 定位 |
| 批次总结走错分支 | 提示词强调"PRACTICE_SUMMARY 由 taskType 直接判定，不走意图路由" |
| 想写 question 表 | 提示词强调"只 SELECT，写入由 Spring 负责" |
| 虚拟环境装错 Python 版本 | 用 `python3.12 -m venv .venv`，明确指定版本 |
| sql/init.sql 没生成 | 提示词里强调"从 AGENTS.md 的数据库表章节完整复制" |

---

## 附：通用提示词模板

临时加需求时用这段：

```
# 角色
资深 Python 后端工程师，精通 FastAPI + Pydantic + OpenAI SDK + SQLAlchemy async。

# 任务
[具体功能]

# 上下文
项目是 FastAPI 0.115 + Pydantic 2.10 + OpenAI SDK 1.57 + SQLAlchemy 2.0 async，
Python 3.12。
已存在 main.py、config.py、schemas.py、db.py、repository.py、
llm_client.py、router.py、handlers/、prompts/、sql/init.sql。

# 约束
- Python 3.12
- 用 async def，不用同步
- 提示词从 prompts/ 读，不硬编码
- LLM 调用加 response_format={"type": "json_object"}
- 只读 question 表，不写
- 禁止引入未列出的依赖
- 接口永远返回 HTTP 200

# 输出规范
1. 先输出方案和文件清单，我确认后再写代码
2. 代码完整，含 import
3. 多文件分文件输出，标注完整路径
```

---

## 附：Spring 端需同步的改动

Agent 接口路径从 `/agent/run` 改为 `/internal/rag/chat`，请求体新增字段。

### AgentRequest 加字段

```java
/** 对话历史 */
private List<Map<String, Object>> messages;

/** 刷题批次 ID，PRACTICE_SUMMARY 时必填 */
private String sessionId;

/** 答对的题目 ID 列表 */
private List<Long> correctQuestionIds;

/** 答错的题目 ID 列表 */
private List<Long> wrongQuestionIds;

/** 用户档案 */
private Map<String, Object> profile;

/** 知识问答 / 院校推荐时必填 */
private String userInput;
```

### AgentClient 请求路径

```java
restClient.post()
        .uri("/internal/rag/chat")   // 原来是 /agent/run
        .body(request)
        .retrieve()
        .body(AgentResponse.class);
```

### TaskService 新增方法

```java
Task submitPracticeSummary(Long userId, String sessionId);
```

实现要点：
1. 查 practice_record，按 sessionId 分组，分出对/错 questionId
2. 查 user，组装 profile
3. 组装 AgentRequest（taskType=PRACTICE_SUMMARY）
4. 调 AgentClient
5. 落 task 表，返回

### PracticeController 新增接口

```java
/**
 * 生成批次总结
 */
@Operation(summary = "生成批次总结", description = "做完一批题后触发 AI 总结")
@PostMapping("/sessions/{sessionId}/summary")
public Result<Task> generateSummary(@PathVariable String sessionId) {
    return Result.ok(taskService.submitPracticeSummary(
            UserContext.currentUserId(), sessionId));
}
```

---

## 环境变量准备

`.env` 内容：

```bash
# LLM
LLM_API_KEY=your_zhipu_api_key
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL_ROUTER=glm-4-flash
LLM_MODEL_MAIN=glm-4-plus

# 内部密钥（与 Spring 端一致）
AGENT_INTERNAL_KEY=kaoyan-agent-internal-key-2026

# 数据库（与 Spring 同一 MySQL，只读 question 表）
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=kaoyan
DB_USER=root
DB_PASSWORD=your_password

# 日志
LOG_LEVEL=INFO
```

---

## 启动顺序

```bash
# 1. 先执行 SQL 建库建表
mysql -u root -p < sql/init.sql

# 2. 创建虚拟环境（明确 3.12）
cd kaoyan-agent
python3.12 -m venv .venv
source .venv/bin/activate
# Windows: py -3.12 -m venv .venv && .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env

# 5. 启动服务
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

---

## 阶段推进概览

| 阶段 | 内容 | 是否必须 | 预估 |
|---|---|---|---|
| 0 | 初始化 + sql/init.sql | 必须 | 15 分钟 |
| 1 | 最小骨架，固定返回 | 必须 | 30 分钟 |
| 2 | 接 LLM + DB + 路由 + 四场景 | 必须 | 2 小时 |
| 3 | 向量库 + RAG | 优化 | 2 小时 |
| 4 | RabbitMQ + Nacos | 优化 | 1.5 小时 |

**先做完 0-2**，三端就能端到端跑通。3-4 留到后面慢慢加。

---

## 端到端流程

1. 前端做完一批题 → Spring 算出对错 ID
2. Spring 调 `/api/practice/sessions/{sessionId}/summary`
3. Spring 组装 AgentRequest 调 Python
4. Python 查 question 表 + 调 LLM 生成总结
5. 返回 Spring，落 task 表
6. 前端展示总结