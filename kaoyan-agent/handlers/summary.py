"""批次总结。"""
import logging
from llm_client import chat as llm_chat
from prompts import get
from repository import get_questions_by_ids
from config import settings

logger = logging.getLogger(__name__)


def _format_questions(questions: list[dict], tag: str) -> str:
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


async def handle(req) -> dict:
    all_ids = list(req.correctQuestionIds or []) + list(req.wrongQuestionIds or [])
    if not all_ids:
        return {
            "summary": "本次练习没有可总结的内容。",
            "accuracy_comment": "",
            "weak_points": [],
            "wrong_analysis": [],
            "next_steps": "",
            "references": [],
        }

    questions = await get_questions_by_ids(all_ids)
    qmap = {q["id"]: q for q in questions}

    correct_list = _format_questions(
        [qmap[i] for i in req.correctQuestionIds if i in qmap], "答对")
    wrong_list = _format_questions(
        [qmap[i] for i in req.wrongQuestionIds if i in qmap], "答错")

    total = len(all_ids)
    correct_count = len(req.correctQuestionIds or [])
    accuracy = round(correct_count / total * 100, 1) if total else 0

    system = get("practice_summary")
    for k, v in {
        "total": total,
        "correct_count": correct_count,
        "accuracy": accuracy,
        "correct_list": correct_list or "（无）",
        "wrong_list": wrong_list or "（无）",
        "target_school": req.profile.get("targetSchool", "未填写"),
        "target_major": req.profile.get("targetMajor", "未填写"),
        "background": req.profile.get("background", "未填写"),
    }.items():
        system = system.replace("${" + k + "}", str(v))
    return await llm_chat(
        model=settings.LLM_MODEL_MAIN, system=system, user="请生成本次练习的总结。"
    )
