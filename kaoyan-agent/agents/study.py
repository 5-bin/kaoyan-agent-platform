"""Study planning over the authoritative profile, with optional consented prose."""

import json
import logging
import re
from decimal import Decimal

from agents.base import StructuredAgent
from core.errors import MODEL_FAILURES, InvalidModelOutput, fallback_reason, failure_reason
from grounding import trusted_numbers
from learning import has_scope, model_allowed, model_messages, safe_learning_context
from prompts import get
from schemas import ConversationRequest, ConversationResolution, StudyPlan

log = logging.getLogger(__name__)

# A sustainable daily ceiling; longer stated availability is not planned as-is.
MAX_DAILY_MINUTES = 720
DURATION = re.compile(r"(\d+(?:\.\d+)?)\s*(小时|分钟|h(?![a-z])|min(?![a-z]))", re.I)
# Scores and rates are facts, not suggestions (“分钟、分析、分类…” are not scores).
SCORE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:分(?!钟|析|类|别|布|配|解|支|组|层|块|段|享|开|割|治|成|期|批|片|量|步)|%|％)"
)
STAT = re.compile(r"(?:作答|答对|答错|做对|做错|正确|错误)\D{0,4}?(\d+(?:\.\d+)?)\s*(?:次|题|道)")
DAY = re.compile(r"第\s*(\d+)\s*天")
# Payload field names and enums must be explained in Chinese, never quoted to users.
INTERNAL_FIELD = re.compile(
    r"(?<![A-Za-z_])(?:questionCount|correctCount|uniqueQuestions|wrongCount|wrongAttempts|accuracy"
    r"|revision|algorithmVersion|blueprintVersion|referenceScore|coverage|independentSamples"
    r"|assistedSamples|unknownSamples|sufficient|masteryIndex|sampleStatus|weight|priority|anomaly"
    r"|learningProfile|availableMinutesPerDay|maxMinutesPerDay|hoursKnown"
    r"|ACTIVE|NOT_DIAGNOSED|INSUFFICIENT|SUFFICIENT|EASY|MEDIUM|HARD)(?![A-Za-z_])"
)


def _minutes(value: str, unit: str) -> float:
    """Convert one stated duration to minutes."""
    return float(value) * (60 if unit.lower() in {"小时", "h"} else 1)


def check_study_plan(plan: StudyPlan, facts: str, available: float | None, days: int) -> None:
    """Reject model plans that break time, score, statistics or period constraints.

    Durations must fit the stated daily availability (never above 12 hours) and
    are not allowed when no availability was given. Scores, percentages and
    attempt counts must already be trusted facts of this turn. Internal payload
    field names and enums are rejected so users only read Chinese explanations.
    """
    limit = min(available, MAX_DAILY_MINUTES) if available else None
    allowed = trusted_numbers(facts)

    def durations(text: str) -> float:
        total = 0.0
        for value, unit in DURATION.findall(text):
            minutes = _minutes(value, unit)
            if limit is None or minutes > limit:
                raise InvalidModelOutput("study_time_exceeded")
            total += minutes
        return total

    for day in plan.days:
        if sum(durations(text) for text in (day.topic, *day.tasks)) > (limit or 0):
            raise InvalidModelOutput("study_time_exceeded")
    for text in plan.basis:
        durations(text)
    for text in (*plan.basis, *(item for day in plan.days for item in (day.topic, *day.tasks))):
        if INTERNAL_FIELD.search(text):
            raise InvalidModelOutput("study_internal_field")
        if any(Decimal(value) not in allowed for value in SCORE.findall(text) + STAT.findall(text)):
            raise InvalidModelOutput("study_number_mismatch")
        if any(not 1 <= int(value) <= days for value in DAY.findall(text)):
            raise InvalidModelOutput("study_period_mismatch")


class StudyPlannerAgent(StructuredAgent):
    """Suggest study work, never mutate mastery coefficients or saved documents."""

    async def handle(
        self, state: tuple[ConversationRequest, ConversationResolution]
    ) -> dict:
        """Build a useful local plan even when external model access is disabled."""
        req, resolution = state
        context = safe_learning_context(req, external=False, plan=resolution)
        stats = context.get("statistics", {})
        profile = stats.get("learningProfile", {})
        points = [item.get("knowledgePoint") for item in profile.get("groups", [])]
        points += [
            item.get("knowledgePoint") or item.get("name")
            for item in stats.get("knowledgePoints", [])
        ]
        points += [item.get("knowledgePoint") for item in context.get("items", [])]
        points = list(dict.fromkeys(str(point)[:255] for point in points if point))
        topics = points[:10] or ["408基础知识"]
        available = re.search(r"每天\s*(\d+(?:\.\d+)?)\s*(小时|分钟)", req.userInput)
        requested = _minutes(available[1], available[2]) if available else None
        minutes = requested if requested and 0 < requested <= MAX_DAILY_MINUTES else None
        if minutes is not None:
            time_basis = f"按你提供的每天{available[1]}{available[2]}安排任务，按实际进度调整。"
        elif requested:
            time_basis = (f"你提供的每天{available[1]}{available[2]}超出可持续上限12小时，未按该时长分配任务；"
                          "请按实际可坚持的时长调整。")
        elif available:
            time_basis = "未提供有效的每日学习时间，未分配具体小时；每天按实际情况调整。"
        else:
            time_basis = "未提供可用学习时间，未分配具体小时；每天按实际情况调整。"
        basis = [
            "按本轮规则画像与有效记录安排，不修改估分或掌握指数。"
            if points
            else "尚无足够个人证据，先做基础复习或可选诊断。",
            time_basis,
        ]
        days = [
            {
                "day": day,
                "topic": topics[(day - 1) % len(topics)],
                "tasks": [
                    "复习审核资料中的定义与适用条件",
                    "独立完成相关审核练习，记录不确定之处",
                    "核对服务器判分并整理错因",
                ],
            }
            for day in range(1, resolution.studyDays + 1)
        ]
        plan = StudyPlan(days=days, basis=basis)
        mode = "rules"
        notice = None
        reason = None
        if model_allowed(req, self.settings) and has_scope(req, "stats"):
            external = safe_learning_context(req, plan=resolution)
            payload = {
                "input": req.userInput,
                "messages": model_messages(req),
                "days": resolution.studyDays,
                "learningContext": external,
                "constraints": {
                    "hoursKnown": minutes is not None,
                    "availableMinutesPerDay": minutes,
                    "maxMinutesPerDay": MAX_DAILY_MINUTES,
                },
            }
            if requested and minutes is None:
                payload["constraints"]["rejectedMinutesPerDay"] = requested
            try:
                candidate = await self.model.generate(get("study_planner"), payload, StudyPlan)
                if len(candidate.days) != resolution.studyDays:
                    raise InvalidModelOutput("study_period_mismatch")
                check_study_plan(candidate, json.dumps(payload, ensure_ascii=False), minutes, resolution.studyDays)
                plan = candidate
                mode = "ai"
            except MODEL_FAILURES as error:
                log.warning("expert=STUDY_PLAN failure=%s reason=%s", type(error).__name__, failure_reason(error))
                mode = "fallback"
                reason = fallback_reason(error)
                notice = "AI规划不可用，已保留规则复习安排。"
        result = {
            "outcome": "COMPLETED",
            "answer": f"已安排{len(plan.days)}天复习建议，可调整后保存为个人笔记。",
            "studyPlan": plan.model_dump(),
            "references": [],
            "explanationMode": mode,
            "conditions": req.conditions.model_dump(),
        }
        if mode == "fallback" and reason:
            result["fallbackReason"] = reason
        if notice:
            result["notice"] = notice
        return result
