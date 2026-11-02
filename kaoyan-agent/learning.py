"""Bounded request planning and model projections. Never executes business tools."""
import re
from typing import Literal
from schemas import StrictModel
from intents import chinese_number, local_document_plan, local_learning_plan, requested_knowledge_point
from pydantic import Field, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema
from config import provider_identifier
from core.runtime import step_model_allowed

__all__ = ["chinese_number", "requested_knowledge_point", "local_document_plan", "local_learning_plan",
           "model_allowed", "has_scope", "model_messages", "clarification_with_example",
           "safe_learning_context", "LearningAnswer", "rule_learning_answer", "weak_point_topics"]


def model_allowed(req, settings):
    return (step_model_allowed.get() and settings.LLM_ENABLED and req.privacy.modelAllowed
            and req.privacy.provider == provider_identifier(settings.LLM_BASE_URL)
            and req.privacy.provider != "unconfigured")


def has_scope(req, scope):
    return scope in req.privacy.scopes


def model_messages(req):
    # Unknown legacy sensitivity is not equivalent to public history.
    return [{"role": m.role, "content": m.content} for m in req.messages
            if m.scopes is not None and set(m.scopes) <= set(req.privacy.scopes)]


def clarification_with_example(message, plan):
    """Compatibility entrypoint; scenario examples live in agents.guidance."""
    from agents.guidance import clarification_with_example as with_example

    return with_example(message, plan)


def _fields(value, keys):
    return {key: value[key] for key in keys if key in value and isinstance(value[key], (str, int, float, bool, type(None)))}


def _with_wrong_attempts(row):
    """Derive wrong attempts in code so the model never has to subtract counts itself."""
    total, correct = row.get("questionCount"), row.get("correctCount")
    if type(total) is int and type(correct) is int and 0 <= correct <= total:
        row["wrongAttempts"] = total - correct
    return row


def safe_learning_context(req, *, external=True, plan=None):
    """Defense in depth: drop identifiers, unrequested records and withheld answers."""
    source = req.learningContext or {}
    plan = plan or req.preparedPlan
    reads = set(plan.reads) if plan else set()
    requested_categories = {"wrong" if value == "practice" else value for value in reads}
    scopes = set(req.privacy.scopes)
    result = {}
    if isinstance(source.get("statistics"), dict) and "stats" in reads and (not external or "stats" in scopes):
        stats = source["statistics"]
        clean = _with_wrong_attempts(_fields(stats, ("questionCount", "correctCount", "uniqueQuestions", "wrongCount", "accuracy", "from", "to", "subject")))
        for name in ("daily", "knowledgePoints"):
            clean[name] = [_with_wrong_attempts(_fields(row, ("date", "statDate", "knowledgePoint", "name", "questionCount", "correctCount", "accuracy", "count", "correct")))
                           for row in stats.get(name, [])[:366] if isinstance(row, dict)]
        profile = stats.get("learningProfile")
        if isinstance(profile, dict):
            safe_profile = _fields(profile, ("revision", "algorithmVersion", "blueprintVersion", "referenceScore", "coverage",
                                             "independentSamples", "assistedSamples", "unknownSamples", "sufficient", "status", "updatedAt"))
            safe_profile["groups"] = [_fields(row, ("subject", "knowledgePoint", "difficulty", "samples", "correct",
                "assisted", "unknown", "masteryIndex", "sampleStatus", "weight", "priority", "anomaly"))
                for row in profile.get("groups", [])[:200] if isinstance(row, dict)]
            clean["learningProfile"] = safe_profile
        result["statistics"] = clean
    items = []
    for item in source.get("items", [])[:20]:
        if not isinstance(item, dict) or not re.fullmatch(r"Q[1-9]\d{0,2}", str(item.get("ref", ""))):
            continue
        kind = item.get("scope", item.get("kind"))
        if kind not in {"wrong", "favorite", "practice", "questions"}:
            # Unknown sensitivity must not be inferred from a model's read plan.
            if external:
                continue
            kind = next((value for value in ("wrong", "favorite", "practice") if value in reads), None)
        category = "wrong" if kind == "practice" else kind
        if category not in requested_categories or external and category != "questions" and category not in scopes:
            continue
        clean = _fields(item, ("ref", "subject", "knowledgePoint", "content", "optionA", "optionB", "optionC", "optionD",
                               "difficulty", "userAnswer", "correct", "answered", "inWrongBook", "version", "snapshotStatus", "snapshotMissing", "notice", "scope", "kind", "matchMethod", "matchTopic"))
        if category == "questions":
            for field in ("userAnswer", "correct", "inWrongBook"):
                clean.pop(field, None)
            clean["answered"] = False
        if category != "questions" and item.get("answered") is True and not item.get("snapshotMissing"):
            clean.update(_fields(item, ("answer", "analysis")))
        items.append(clean)
    if items:
        result["items"] = items
        source_categories = source.get("scope", [])
        if not isinstance(source_categories, list):
            source_categories = [source_categories]
        source_categories = {"wrong" if value == "practice" else value for value in source_categories}
        # A union total may reveal the size of an unconsented collection even
        # when every emitted item individually passes its category check.
        if not external or (source_categories <= scopes | {"questions"} and len(items) == len(source.get("items", [])[:20])):
            result.update(_fields(source, ("total", "readCount", "notice")))
        else:
            result["readCount"] = len(items)
            result["notice"] = "仅包含本轮已授权类别的记录节选；其他类别总量未提供。"
    if "documents" in reads:
        docs = []
        for item in source.get("documents", [])[:5]:
            if not isinstance(item, dict):
                continue
            # Published materials are public. Personal notes require the explicit
            # selected document path and document scope, never this collection.
            if item.get("personal") or item.get("kind") in {"personal", "personal_document"}:
                continue
            if not re.fullmatch(r"D[1-9]\d{0,2}", str(item.get("ref", ""))):
                continue
            docs.append(_fields(item, ("ref", "title", "content", "locator", "version", "excerpt", "truncated", "source")))
        result["documents"] = docs
    refs = {item["ref"] for name in ("items", "documents") for item in result.get(name, [])}
    if "statistics" in result:
        refs.update(str(e.get("ref")) for e in source.get("evidence", [])
                    if isinstance(e, dict) and e.get("kind") in {"stats", "statistics"})
    result["evidence"] = [_fields(item, ("ref", "kind", "title", "locator", "version"))
                          for item in source.get("evidence", [])[:30]
                          if isinstance(item, dict) and item.get("ref") in refs]
    if not external:
        result.update(_fields(source, ("retrievalStatus", "notice", "matchTopic")))
    return result


class LearningExplanation(StrictModel):
    """One public concept explanation with its own reviewed sources."""

    text: str = Field(min_length=1, max_length=1000)
    sourceIds: list[str] = Field(min_length=1, max_length=5)


class LearningSuggestion(StrictModel):
    """A bounded suggestion selection; the service authors all displayed prose."""

    action: Literal["REVIEW_CONCEPT", "REVIEW_ATTEMPT", "COLLECT_SAMPLES", "PRACTICE_RELATED"]
    evidenceRefs: list[str] = Field(default_factory=list, max_length=5)
    sourceIds: list[str] = Field(default_factory=list, max_length=5)


class LearningAnswer(StrictModel):
    """Structured enrichment; legacy prose is parsed only to reject it safely."""

    explanations: list[LearningExplanation] = Field(default_factory=list, max_length=5)
    suggestions: list[LearningSuggestion] = Field(default_factory=list, max_length=5)
    answer: str | None = Field(default=None, min_length=1, max_length=12000)
    evidenceRefs: list[str] = Field(default_factory=list, max_length=30)
    sourceIds: list[str] = Field(default_factory=list, max_length=5)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        """Do not invite new providers to populate legacy free-form fields."""
        schema = handler.resolve_ref_schema(handler(core_schema))
        for name in ("answer", "evidenceRefs", "sourceIds"):
            schema["properties"].pop(name, None)
        return schema


# Mirrors LearningProfileEngine: the profile is not the interval statistics above.
PROFILE_BASIS = ("以下规则画像与上面的区间统计口径不同：统计全部历史中的独立作答，同一题7天内只计1次，"
                 "不含提示辅助及未记录提示情况的作答，按难度分组且每组最多取最近50条；两组次数不能直接比较。")


def rule_learning_answer(context, plan):
    if plan.operation == "PRACTICE_CREATE":
        return "已识别组题请求，可练习题目与实际题量由业务后端核对。请通过练习卡片进入刷题页面作答。"
    lines = []
    if context.get("notice"):
        lines.append(context["notice"])
    if context.get("matchTopic"):
        lines.append("筛选主题：" + context["matchTopic"])
    stats = context.get("statistics")
    if stats:
        count = stats.get("questionCount", 0)
        if not count:
            lines.append("所选区间暂无有效已提交作答，不能据此判断掌握程度。")
        else:
            lines.append(f"记录事实：{stats.get('from', '')}至{stats.get('to', '')}有效作答{count}次，正确{stats.get('correctCount', 0)}次，去重题数{stats.get('uniqueQuestions', '未记录')}。")
            if "wrongAttempts" in stats:
                lines.append(f"区间内错误作答{stats['wrongAttempts']}次；与当前错题本题数分别统计。")
            accuracy = stats.get("accuracy")
            if type(accuracy) in (int, float) and 0 <= accuracy <= 1:
                lines.append(f"区间正确率{accuracy * 100:.1f}%，口径为全部有效已提交作答。")
        lines.extend(_knowledge_point_lines(stats.get("knowledgePoints", [])))
        lines.append("学习时长与提示辅助：未记录；区间作答次数不区分是否独立完成。")
        profile = stats.get("learningProfile", {})
        if profile:
            lines.append(PROFILE_BASIS)
            lines.append(f"当前规则画像版本{profile.get('revision', 0)}，独立证据{profile.get('independentSamples', 0)}条；408实验性参考分：{profile.get('referenceScore') if profile.get('referenceScore') is not None else '证据或审核蓝图不足'}。未经完整试卷校准。")
            lines.extend(_profile_group_lines(profile.get("groups", [])[:10]))
    items = context.get("items", [])
    if items:
        lines.append(f"本次读取{len(items)}条记录，总量{context.get('total', len(items))}；列表节选不代表全部学习情况。")
        for item in items:
            lines.append(f"[{item['ref']}] {item.get('knowledgePoint') or item.get('subject') or '题目'}："
                         + (("知识点匹配" if item.get("matchMethod") == "LABEL" else "语义相关") + "；" if item.get("matchMethod") else "")
                         + (item.get("content", "")[:180] + "；" if item.get("matchMethod") else "")
                         + ("历史快照缺失，不能补造当时题干与答案。" if item.get("snapshotMissing") else
                            "尚未提交，标准答案与完整解析保持隐藏。" if not item.get("answered") else
                            "最近一次已提交作答正确；仍保留在错题本。" if item.get("inWrongBook") and item.get("correct") == 1 else
                            "已提交作答，可据该版本回顾。"))
    for doc in context.get("documents", []):
        lines.append(f"[{doc['ref']}] {doc.get('title', '备考资料')}：{(doc.get('content') or doc.get('excerpt') or '')[:1500]}")
    tail = []
    if plan.operation != "NONE":
        tail.append("已识别操作意图，是否执行以及执行结果由业务后端核验；需要确认的操作请先查看预览。")
    if not lines and not tail:
        lines.append("没有读取到本次请求所需记录。请明确对象或筛选范围；未授权外发时仍可使用本地页面功能。")
    if context.get("retrievalStatus") == "READY" and not items:
        tail.append("没有找到符合该主题的题目，未修改记录。")
    return bounded_lines(lines, tail)


SMALL_SAMPLE = 5
# Keeps the merged small-sample line well inside one bounded answer line.
MERGED_NAME_LIMIT = 30
DIFFICULTY_LABELS = {"EASY": "简单", "MEDIUM": "中等", "HARD": "困难"}


def _point_counts(point: dict) -> tuple[str, int, int | None]:
    """Return the name, interval attempts and correct attempts of one statistics row."""
    name = point.get("knowledgePoint", point.get("name", "未标注知识点"))
    count = point.get("questionCount", point.get("count", 0))
    return name, count, point.get("correctCount", point.get("correct"))


def _error_rate(point: dict) -> float:
    """Sort key only; rows without a correct count rank after known error rates."""
    _, count, correct = _point_counts(point)
    return (count - correct) / count if count and correct is not None else -1.0


def _merged_names(items: list[str]) -> str:
    """Join at most MERGED_NAME_LIMIT names and state how many were left out."""
    shown = "、".join(items[:MERGED_NAME_LIMIT])
    return shown + (f"等{len(items)}个，其余{len(items) - MERGED_NAME_LIMIT}个未在文字中展示，请在学习统计页面查看"
                    if len(items) > MERGED_NAME_LIMIT else "")


def _knowledge_point_lines(points: list[dict]) -> list[str]:
    """List judgeable points by error rate first and merge small samples into one line."""
    lines: list[str] = []
    enough = [p for p in points if _point_counts(p)[1] >= SMALL_SAMPLE]
    small = [p for p in points if _point_counts(p)[1] < SMALL_SAMPLE]
    for point in sorted(enough, key=lambda p: (-_error_rate(p), -_point_counts(p)[1])):
        name, count, correct = _point_counts(point)
        lines.append(f"{name}：区间内有效作答{count}次（同题重复作答分别计数）"
                     + (f"，正确{correct}次" if correct is not None else "") + "；可结合具体错题分析可能错因。")
        if "wrongAttempts" in point:
            lines.append(f"{name}：区间内错误作答{point['wrongAttempts']}次。")
    if small:
        small.sort(key=lambda p: -_point_counts(p)[1])
        names = []
        for point in small:
            name, count, correct = _point_counts(point)
            wrong = point.get("wrongAttempts")
            detail = f"，错误{wrong}次" if wrong is not None else f"，正确{correct}次" if correct is not None else ""
            names.append(f"{name}（{count}次{detail}）")
        lines.append(f"以下{len(small)}个知识点区间内有效作答均样本不足5次，暂不判断掌握程度，可作为补练候选："
                     + _merged_names(names) + "。")
    return lines


def weak_point_topics(points: list[dict], limit: int = 5) -> list[str]:
    """Rank interval points for retrieval: judgeable high error rates first, then most wrong attempts.

    Small samples only fill remaining slots; ranking never becomes a mastery conclusion.
    """
    def wrong(point: dict) -> int | None:
        _, count, correct = _point_counts(point)
        return point.get("wrongAttempts", count - correct if correct is not None else None)

    enough = sorted((p for p in points if _point_counts(p)[1] >= SMALL_SAMPLE),
                    key=lambda p: (-_error_rate(p), -_point_counts(p)[1]))
    # Points known to have no wrong attempt are dropped; unknown correctness is kept.
    small = sorted((p for p in points if _point_counts(p)[1] < SMALL_SAMPLE and wrong(p) != 0),
                   key=lambda p: (-(wrong(p) or 0), -_point_counts(p)[1]))
    names = [_point_counts(p)[0] for p in enough + small]
    return list(dict.fromkeys(str(name)[:100] for name in names if name))[:limit]


def _profile_group_lines(groups: list[dict]) -> list[str]:
    """Keep anomalies and sufficient groups apart; merge groups that only need more samples."""
    lines: list[str] = []
    small = []
    for group in groups:
        name = group.get("knowledgePoint", "知识点")
        difficulty = DIFFICULTY_LABELS.get(group.get("difficulty", ""), group.get("difficulty", "") or "未分难度")
        samples = group.get("samples", 0)
        if group.get("anomaly"):
            lines.append(f"{name}（{difficulty}）：独立样本{samples}条，近期表现异常，可核对是否猜题、概念混淆或操作失误。")
        elif samples < SMALL_SAMPLE:
            small.append(f"{name}（{difficulty}，{samples}条）")
        else:
            lines.append(f"{name}（{difficulty}）：独立样本{samples}条，按复习优先级安排巩固与进阶练习。")
    if small:
        lines.append("以下画像分组独立样本不足5条，建议补充独立样本：" + _merged_names(small) + "。")
    return lines


# Leaves room for appended reviewed excerpts within the 20000-character result.
RULE_ANSWER_LIMIT = 16000


def bounded_lines(lines, tail):
    """Keep whole lines within the limit and state how many were not shown."""
    budget = RULE_ANSWER_LIMIT - sum(len(line) + 1 for line in tail) - 60
    shown = []
    for line in lines:
        if len(line) + 1 > budget:
            break
        shown.append(line)
        budget -= len(line) + 1
    if len(shown) < len(lines):
        shown.append(f"……另有{len(lines) - len(shown)}条记录未在文字中展示，请在对应页面查看完整内容。")
    return "\n".join(shown + tail)
