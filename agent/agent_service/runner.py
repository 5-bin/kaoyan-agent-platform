import logging
from time import perf_counter
from .knowledge import KnowledgeBase
from .model_client import ModelClient
from .schemas import RunRequest, RunResult
from .tools import inspect_text
from .releases import DemoReleaseProvider
from .retrieval import Retriever
from . import workflows

logger = logging.getLogger(__name__)


class Runner:
    def __init__(self, settings, model=None):
        self.settings = settings
        self.releases = DemoReleaseProvider(settings.knowledge_path)
        self.knowledge: Retriever = self.releases.load("demo-408-v1")
        self.model = model or ModelClient(settings)

    def run(self, request: RunRequest):
        started = perf_counter()
        task_id = str(request.taskId)
        if request.taskType != "knowledge_qa":
            workflow = getattr(workflows, request.taskType)
            result = workflow(request, self.settings.mode)
            result.latencyMs = round((perf_counter() - started) * 1000)
            return result
        result = RunResult(taskId=task_id, status="unsupported", mode=self.settings.mode,
                           answer="当前资料没有覆盖这个任务，请补充相关资料或选择已覆盖的任务。")
        if len(request.input) < 8:
            result.status = "needs_input"
            result.answer = "请补充任务目标、使用场景和希望得到的结果。"
            result.followUp = ["你要完成什么具体任务？", "有哪些材料或约束？"]
        else:
            documents = self.knowledge.search(request.input, subject=request.context.subject)
            if documents:
                stats = inspect_text(request.input)
                if self.settings.mode == "demo":
                    result.status = "completed"
                    result.answer = (
                        "【离线工程演示，未调用大模型；资料待人工审核】已匹配以下408演示资料，不作为正式备考答案：\n"
                        + "\n".join(f"{doc.title}：{doc.content}" for doc in documents)
                        + f"\n文本统计工具：{stats['characters']}个字符，{stats['nonemptyLines']}行非空内容。"
                    )
                    result.steps = ["检查输入", "按关键词检索自编演示资料", "执行文本统计工具", "组装结果和出处"]
                    result.sources = [doc.source() for doc in documents]
                    result.data = {"knowledgePointIds": [doc.id for doc in documents], "reviewStatus": "demo_unreviewed"}
                else:
                    try:
                        payload = {"input": request.input, "toolResults": {"inspect_text": stats},
                                   "references": [{"id": doc.id, "content": doc.content, "locator": doc.locator} for doc in documents]}
                        answer = self.model.generate(payload)
                        mapping = {doc.id: doc for doc in documents}
                        if any(source_id not in mapping for source_id in answer.sourceIds):
                            raise ValueError("unknown_source")
                        if answer.status == "completed" and not answer.sourceIds:
                            raise ValueError("missing_sources")
                        if answer.status == "needs_input" and not answer.followUp:
                            raise ValueError("missing_followup")
                        result.status, result.answer = answer.status, answer.answer
                        result.answer = "【模型接口验证；演示资料待人工审核】\n" + result.answer
                        result.data = {"reviewStatus": "demo_unreviewed"}
                        result.steps, result.followUp = answer.steps, answer.followUp
                        result.sources = [mapping[source_id].source() for source_id in dict.fromkeys(answer.sourceIds)]
                    except Exception as error:
                        logger.warning("task=%s modelFailure=%s", task_id, type(error).__name__)
                        result.status = "failed"
                        result.answer = "模型调用、引用或结果格式检查失败，请稍后重试；管理员可按任务编号检查日志。"
        result.latencyMs = round((perf_counter() - started) * 1000)
        logger.info("task=%s status=%s mode=%s", task_id, result.status, result.mode)
        return result
