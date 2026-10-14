"""院校推荐。"""
from llm_client import chat as llm_chat
from prompts import get
from config import settings


async def handle(user_input: str, profile: dict, messages: list) -> dict:
    system = get("tuijian_yuanxiao")
    for k, v in {
        "target_major": profile.get("targetMajor", "未填写"),
        "exam_year": profile.get("examYear", "未填写"),
        "background": profile.get("background", "未填写"),
        "target_school": profile.get("targetSchool", "未填写"),
        "user_input": user_input or "",
        "rag_context": "暂无参考资料",
    }.items():
        system = system.replace("${" + k + "}", str(v))
    return await llm_chat(
        model=settings.LLM_MODEL_MAIN, system=system, user=user_input or ""
    )
