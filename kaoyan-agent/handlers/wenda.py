"""408 知识问答。"""
from llm_client import chat as llm_chat
from prompts import get
from config import settings


async def handle(user_input: str, profile: dict, messages: list) -> dict:
    system = get("zhishi_wenda")
    for k, v in {
        "user_input": user_input or "",
        "messages": "\n".join(str(m) for m in messages[-6:]),
        "rag_context": "暂无参考资料",
    }.items():
        system = system.replace("${" + k + "}", str(v))
    return await llm_chat(
        model=settings.LLM_MODEL_MAIN, system=system, user=user_input or ""
    )
