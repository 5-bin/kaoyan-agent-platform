"""Compatibility service delegating domain execution to HelloAgents experts."""

from agents.knowledge import KnowledgeAgent
from agents.results import finalize_result
from agents.school import SchoolAgent
from agents.summary import SummaryAgent
from config import Settings
from core.model import ModelClient
from agents.resolver import PlanResolver
from retrieval import Corpus, Retriever
from schemas import ChatRequest
from tools.knowledge import KnowledgeSearchTool
from tools.registry import StrictToolRegistry, ValidatedTool
from tools.schools import Admission

class Workflows:
    """Keep old task callers and dependency injection points stable."""

    def __init__(
        self,
        settings: Settings,
        corpus: Corpus,
        retriever: Retriever,
        model: ModelClient,
        knowledge_search: ValidatedTool | None = None,
        admission_links: ValidatedTool | None = None,
    ) -> None:
        """Assemble immutable resources once; agents remain request-scoped."""
        self.settings, self.corpus, self.retriever, self.model = (
            settings,
            corpus,
            retriever,
            model,
        )
        self.tools = StrictToolRegistry()
        self.knowledge_search = self.tools.add(
            knowledge_search
            if knowledge_search is not None
            else KnowledgeSearchTool(retriever)
        )
        self.admission_links = (
            self.tools.add(admission_links) if admission_links is not None else None
        )
        self.programs = [
            (Admission.model_validate(d.metadata), d)
            for d in corpus.documents
            if d.domain == "school"
        ]
        if len({p.programId for p, _ in self.programs}) != len(self.programs):
            raise ValueError("招生专业编号重复")

    async def qa(self, req: ChatRequest) -> dict:
        """Execute one knowledge expert."""
        return await KnowledgeAgent(self).execute(req)

    async def tutor(self, req: ChatRequest) -> dict:
        """Use the same native knowledge expert as the main conversation."""
        return await KnowledgeAgent(self).execute(req)

    async def schools(self, req: ChatRequest) -> dict:
        """Execute one school expert, including deterministic candidate filtering."""
        return await SchoolAgent(self).execute(req)

    async def summary(self, req: ChatRequest) -> dict:
        """Execute one summary specialization of the knowledge tutor."""
        return await SummaryAgent(self).execute(req)

    async def run(self, req: ChatRequest) -> dict:
        """Dispatch one legacy task without changing its result envelope."""
        task_type = req.taskType
        if task_type == "CHAT":
            task_type = await self.resolve(req, allow_model=False)
        if task_type == "SCHOOL_RECOMMEND":
            result = await self.schools(req)
        elif task_type == "KNOWLEDGE_QA":
            result = await self.qa(req)
        elif task_type == "WRONG_QUESTION_TUTOR":
            result = await self.tutor(req)
        elif task_type == "PRACTICE_SUMMARY":
            result = await self.summary(req)
        else:
            result = {
                "outcome": "NEEDS_INPUT",
                "answer": "请明确单项408知识或择校目标；复合请求、学情分析及笔记操作请前往主助手 /tasks。",
                "followUp": ["你要咨询408概念还是院校专业？"],
            }
        result["resolvedTaskType"] = task_type
        result["retrievalBackend"] = self.settings.RAG_BACKEND
        return finalize_result(result, self.corpus.release_id, task_type)

    async def resolve(self, req: ChatRequest, allow_model: bool = True) -> str:
        """Delegate legacy routing to the same bounded conversation resolver."""
        return await PlanResolver(self).legacy(req, allow_model=allow_model)
