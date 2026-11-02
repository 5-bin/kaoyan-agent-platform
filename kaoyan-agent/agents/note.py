"""HelloAgents domain implementation preserving the existing business rules."""

import logging

from agents.base import StructuredAgent
from agents.results import StepContext
from core.errors import MODEL_FAILURES, ModelUnavailable, fallback_reason, failure_reason
from core.runtime import step_model_allowed
from learning import has_scope, model_allowed, model_messages, safe_learning_context
from prompts import get
from schemas import (
    ConversationRequest,
    ConversationResolution,
    DocumentDraft,
)

from tools.registry import (
    EmptyParameters,
    InstructionParameters,
    StrictToolRegistry,
    ValidatedTool,
)


log = logging.getLogger(__name__)


class NoteAgent(StructuredAgent):
    """One request-scoped domain expert."""

    def __init__(
        self, owner: StructuredAgent, *, dependencies: StepContext | None = None
    ) -> None:
        """Receive only the coordinator's explicitly declared typed dependency."""
        super().__init__(owner)
        self.dependencies = dependencies or StepContext()

    async def handle(
        self, state: tuple[ConversationRequest, ConversationResolution]
    ) -> dict:
        """Produce a previewable draft; Java remains responsible for saving it."""
        req, resolution = state
        conditions = self.base(req, resolution)
        result = {
            "outcome": "NEEDS_INPUT",
            "answer": "",
            "conditions": conditions,
            "operation": resolution.action,
            "references": [],
        }
        if self.dependencies.study_plan is not None:
            plan = self.dependencies.study_plan
            updating = resolution.action == "DOCUMENT_UPDATE" and req.document is not None
            content = "# 复习计划\n\n" + "\n".join(plan.basis)
            for day in plan.days:
                content += f"\n\n## 第{day.day}天：{day.topic}\n" + "\n".join(
                    "- " + task for task in day.tasks
                )
            if updating:
                content = req.document.content + "\n\n" + content
            draft = DocumentDraft(
                title=req.document.title if updating else "复习计划",
                content=content,
            )
            result.update(
                outcome="COMPLETED",
                answer="复习计划已整理为笔记建议，请预览后确认保存。",
                explanationMode="rules",
                documentProposal={
                    "operation": "update" if updating else "create",
                    "documentId": req.document.id if updating else None,
                    "baseVersion": req.document.version if updating else None,
                    **draft.model_dump(),
                },
            )
            return result
        if resolution.clarification:
            result["answer"] = resolution.clarification
        elif resolution.action == "DOCUMENT_UPDATE" and req.document is None:
            result["answer"] = "请先选择要修改的个人笔记。"
        elif not model_allowed(req, self.engine.settings):
            result.update(
                outcome="UNSUPPORTED",
                answer="AI笔记生成未启用或未获得外发授权；你仍可在个人笔记中手动创建和编辑。"
                if step_model_allowed.get() else "本轮模型额度已分配给优先专家，未生成笔记建议；可单独发起笔记请求。",
            )
        elif req.document is not None and (not has_scope(req, "document")):
            result.update(
                outcome="UNSUPPORTED",
                answer="所选个人笔记未获本次外发授权，请授权并逐份选择后再生成修改建议。",
            )
        else:
            registry = StrictToolRegistry()

            def read_document() -> dict[str, str | int] | None:
                """读取本轮已授权文档快照。个人笔记不是审核资料。"""
                return (
                    {
                        "ref": "D1",
                        "title": req.document.title,
                        "content": req.document.content,
                        "version": req.document.version,
                    }
                    if req.document
                    else None
                )

            read_tool = registry.add(
                ValidatedTool(
                    "read_document",
                    "读取本轮授权笔记快照",
                    EmptyParameters,
                    read_document,
                )
            )

            async def propose(instruction: str) -> DocumentDraft:
                return await self.engine.model.generate(
                    get("note_expert_0"),
                    {
                        "instruction": instruction,
                        "document": read_tool.invoke({}),
                        "messages": model_messages(req),
                        "learningContext": safe_learning_context(req, plan=resolution),
                    },
                    DocumentDraft,
                )

            propose_tool = registry.add(
                ValidatedTool(
                    "propose_document",
                    "生成待确认笔记建议",
                    InstructionParameters,
                    propose,
                    DocumentDraft.model_validate,
                )
            )
            try:
                draft = await propose_tool.ainvoke({"instruction": req.userInput})
            except MODEL_FAILURES as error:
                log.warning("expert=NOTE failure=%s reason=%s", type(error).__name__, failure_reason(error))
                result.update(
                    outcome="UNSUPPORTED",
                    answer="笔记建议暂时无法生成，请稍后重试或手动整理。",
                    explanationMode="fallback",
                    fallbackReason=fallback_reason(error),
                    notice="模型调用或输出校验未完成，未生成或保存笔记。",
                )
                if isinstance(error, ModelUnavailable) and error.args == ("context_budget_exceeded",):
                    result.update(
                        answer="必要原文超出本轮输入预算，未生成笔记建议；请缩小请求范围或手动编辑。",
                        notice="原文未截断，未发送模型请求，也未生成或保存替换建议。",
                    )
                return result
            result.update(
                outcome="COMPLETED",
                answer="笔记建议已生成，请预览差异后确认保存。",
                explanationMode="ai",
                documentProposal={
                    "operation": "update"
                    if req.document and resolution.action == "DOCUMENT_UPDATE"
                    else "create",
                    "documentId": req.document.id
                    if req.document and resolution.action == "DOCUMENT_UPDATE"
                    else None,
                    "baseVersion": req.document.version
                    if req.document and resolution.action == "DOCUMENT_UPDATE"
                    else None,
                    **draft.model_dump(),
                },
            )
        return result
