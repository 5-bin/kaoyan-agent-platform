"""意图路由。"""
from llm_client import chat as llm_chat
from prompts import get
from config import settings


async def route(user_input: str, messages: list) -> dict:
    system = get("intent_router")
    history = "\n".join(str(m) for m in messages[-6:])
    user = f"用户输入：{user_input}\n对话历史：{history}"
    return await llm_chat(model=settings.LLM_MODEL_ROUTER, system=system, user=user)
