"""Synthetic characterization cases captured before the HelloAgents migration."""

import copy
import json

from core.errors import ModelUnavailable
from config import Settings
from conversation import ConversationWorkflow
from retrieval import Corpus, Retriever
from schemas import ChatRequest, ConversationRequest
from workflows import Workflows


class RecordingModel:
    """Record exact logical model inputs without contacting a provider."""

    def __init__(self, failure: bool = False) -> None:
        self.calls: list[dict] = []
        self.failure = failure

    async def generate(self, instruction, payload, schema, router=False):
        self.calls.append(
            copy.deepcopy(
                {
                    "instruction": instruction,
                    "payload": payload,
                    "schema": schema.__name__,
                    "router": router,
                }
            )
        )
        if self.failure:
            raise ModelUnavailable("synthetic-provider-failure")
        values = {
            "Answer": {
                "answer": "线程共享地址空间，保留各自的栈。",
                "sourceIds": ["os-threads#0"],
            },
            "ConversationResolution": {
                "action": "KNOWLEDGE_QA",
                "standaloneQuery": payload.get("input", "线程"),
            },
            "DocumentDraft": {
                "title": "合成笔记",
                "content": "# 合成笔记\n线程共享地址空间。",
            },
            "Summary": {"summary": "合成总结：复习线程。"},
            "LearningAnswer": {
                "answer": "样本不足，建议复习线程。",
                "evidenceRefs": [],
                "sourceIds": [],
            },
        }
        if schema.__name__ == "Explanations":
            value = {
                "explanations": [
                    {
                        "programId": item["programId"],
                        "text": item["explanation"],
                        "sourceIds": item["sourceIds"],
                    }
                    for item in payload["candidates"]
                ]
            }
        else:
            value = values[schema.__name__]
        return schema.model_validate(value)

    async def close(self) -> None:
        """No provider resources are opened."""


def cases() -> list[dict]:
    """Cover legacy branches whose behavior must survive migration exactly."""
    base = {
        "taskId": "freeze",
        "userId": 1,
        "taskType": "KNOWLEDGE_QA",
        "userInput": "进程与线程",
    }
    consent = {
        "modelAllowed": True,
        "scopes": ["profile", "wrong", "stats", "document"],
        "provider": "https://open.bigmodel.cn/api/paas/v4",
    }
    result = []

    def add(name, entry="workflow", enabled=False, failure=False, **body):
        result.append(
            {
                "name": name,
                "entry": entry,
                "enabled": enabled,
                "failure": failure,
                "request": {**base, **body},
            }
        )

    add("qa_rules")
    add("qa_ai", enabled=True, privacy=consent)
    add("qa_failure", enabled=True, failure=True, privacy=consent)
    add("qa_no_consent", enabled=True)
    add("qa_no_data", userInput="量子场论重整化")
    add("chat_local", taskType="CHAT", enabled=True, privacy=consent)
    for region in ([], ["江苏"], ["广东"]):
        add(
            "schools_" + str(region),
            taskType="SCHOOL_RECOMMEND",
            userInput="推荐院校",
            profile={"examYear": 2027, "targetMajor": "081200"},
            preferences={
                "degreeType": "academic",
                "regions": region,
                "regionConstraint": "required",
            },
        )
    add(
        "schools_ai",
        taskType="SCHOOL_RECOMMEND",
        userInput="推荐院校",
        enabled=True,
        privacy=consent,
        profile={"examYear": 2027, "targetMajor": "081200"},
        preferences={"degreeType": "academic"},
    )
    add("schools_missing", taskType="SCHOOL_RECOMMEND", userInput="推荐院校")
    for enabled in (False, True):
        add(
            "summary_" + str(enabled),
            taskType="PRACTICE_SUMMARY",
            userInput=None,
            sessionId="synthetic",
            enabled=enabled,
            privacy=consent,
            questions=[
                {
                    "id": 1,
                    "version": 1,
                    "subject": "操作系统",
                    "knowledgePoint": "线程",
                    "content": "合成题",
                    "answer": "A",
                    "correct": False,
                }
            ],
        )
    add(
        "summary_empty",
        taskType="PRACTICE_SUMMARY",
        userInput=None,
        sessionId="synthetic",
    )
    add(
        "followup",
        entry="conversation",
        taskType="CHAT",
        userInput="它们共享什么",
        messages=[{"role": "user", "content": "进程与线程"}],
    )
    add("clarification", entry="conversation", taskType="CHAT", userInput="它们是什么")
    add(
        "document_disabled",
        entry="conversation",
        taskType="CHAT",
        userInput="创建一份线程笔记",
    )
    add(
        "document_ai",
        entry="conversation",
        taskType="CHAT",
        userInput="创建一份线程笔记",
        enabled=True,
        privacy=consent,
    )
    add(
        "document_missing",
        entry="conversation",
        taskType="CHAT",
        userInput="修改这份笔记",
    )
    for enabled in (False, True):
        add(
            "learning_" + str(enabled),
            entry="conversation",
            taskType="CHAT",
            userInput="分析学情",
            enabled=enabled,
            privacy=consent,
            preparedPlan={
                "action": "LEARNING_ANALYSIS",
                "standaloneQuery": "分析学情",
                "reads": ["stats"],
            },
            learningContext={
                "statistics": {
                    "questionCount": 3,
                    "correctCount": 1,
                    "knowledgePoints": [],
                }
            },
        )
    return result


async def execute(case: dict) -> dict:
    """Execute the same case against either implementation."""
    settings = Settings(
        _env_file=None,
        AGENT_INTERNAL_KEY="synthetic-freeze-key-12345",
        RAG_BACKEND="lexical",
        LLM_ENABLED=case["enabled"],
        LLM_API_KEY="synthetic" if case["enabled"] else "",
    )
    model = RecordingModel(case["failure"])
    corpus = Corpus(settings.RAG_DATA)
    retriever = Retriever(settings, corpus)
    engine = Workflows(settings, corpus, retriever, model)
    try:
        if case["entry"] == "conversation":
            result = await ConversationWorkflow(engine).run(
                ConversationRequest.model_validate(copy.deepcopy(case["request"]))
            )
        else:
            result = await engine.run(
                ChatRequest.model_validate(copy.deepcopy(case["request"]))
            )
        return json.loads(
            json.dumps({"result": result, "calls": model.calls}, ensure_ascii=False)
        )
    finally:
        retriever.close()
