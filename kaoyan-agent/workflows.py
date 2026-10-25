"""Deterministic workflows with an optional, constrained explanation layer."""
import asyncio
import logging
from pydantic import Field
from schemas import StrictModel, Answer, Intent, Explanations, Summary, TutorExplanation
from prompts import get

log = logging.getLogger(__name__)


class Admission(StrictModel):
    programId: str
    school: str
    college: str
    major: str
    majorCode: str
    year: int = Field(ge=2000, le=2100)
    degreeType: str
    region: str
    studyMode: str
    examSubjects: list[str]
    updatedAt: str


class Workflows:
    def __init__(self, settings, corpus, retriever, model):
        self.settings, self.corpus, self.retriever, self.model = settings, corpus, retriever, model
        self.programs = [(Admission.model_validate(d.metadata), d) for d in corpus.documents if d.domain == "school"]
        if len({p.programId for p, _ in self.programs}) != len(self.programs):
            raise ValueError("招生专业编号重复")

    async def run(self, req):
        task_type = req.taskType
        if task_type == "CHAT":
            task_type = await self.resolve(req)
        if task_type == "SCHOOL_RECOMMEND":
            result = await self.schools(req)
        elif task_type == "KNOWLEDGE_QA":
            result = await self.qa(req)
        elif task_type == "PRACTICE_SUMMARY":
            result = await self.summary(req)
        elif task_type == "WRONG_QUESTION_TUTOR":
            result = await self.tutor(req)
        else:
            result = {"outcome": "NEEDS_INPUT", "answer": "请明确你想了解的408知识，或提供择校目标。",
                      "followUp": ["你要咨询408概念还是院校专业？"]}
        result.setdefault("references", [])
        result.setdefault("explanationMode", "rules")
        result["resolvedTaskType"] = task_type
        result["retrievalBackend"] = self.settings.RAG_BACKEND
        result["releaseId"] = self.corpus.release_id
        return result

    async def resolve(self, req):
        text = req.userInput or ""
        school = any(w in text for w in ("择校", "院校", "报考", "推荐学校", "推荐大学", "推荐专业"))
        knowledge = any(word.lower() in text.lower() for d in self.corpus.documents
                        if d.domain == "knowledge" for word in d.keywords)
        if school and knowledge:
            return "CHAT"
        if school:
            return "SCHOOL_RECOMMEND"
        if knowledge:
            return "KNOWLEDGE_QA"
        if self.settings.LLM_ENABLED:
            try:
                answer = await self.model.generate(get("intent_router"),
                    {"input": text, "messages": [m.model_dump() for m in req.messages]}, Intent, router=True)
                return answer.intent
            except Exception as e:
                log.warning("routerFailure=%s", type(e).__name__)
        return "CHAT"

    async def qa(self, req):
        docs = await asyncio.to_thread(self.retriever.search, req.userInput, "knowledge", 5)
        if not docs:
            return {"outcome": "UNSUPPORTED", "answer": "当前审核资料未覆盖该问题，请缩小问题范围或补充资料。"}
        result = {"outcome": "COMPLETED", "answer": "以下为来源摘要：\n" + "\n".join(d.content for d in docs),
                  "references": [d.reference().model_dump() for d in docs], "explanationMode": "rules"}
        if self.settings.LLM_ENABLED:
            try:
                answer = await self.model.generate(get("zhishi_wenda"),
                    {"input": req.userInput, "messages": [m.model_dump() for m in req.messages],
                     "references": [{"id": d.id, "content": d.content} for d in docs]}, Answer)
                ids = set(answer.sourceIds)
                if not ids <= {d.id for d in docs}:
                    raise ValueError("unknown_source")
                result.update(answer=answer.answer, explanationMode="ai",
                    references=[d.reference().model_dump() for d in docs if d.id in ids])
            except Exception as e:
                log.warning("qaModelFailure=%s", type(e).__name__)
                result.update(explanationMode="fallback", notice="AI解释不可用，已保留来源摘要。")
        return result

    async def schools(self, req):
        profile, pref = req.profile, req.preferences
        majors = pref.majorCodes or []
        if not majors and profile.targetMajor:
            majors = sorted({p.majorCode for p, _ in self.programs
                if profile.targetMajor in {p.majorCode, p.major}})
        missing = []
        if not profile.examYear:
            missing.append("请在个人档案填写报考年份")
        if not majors:
            missing.append("请选择目标专业代码（首批081200、085404）")
        if not pref.degreeType:
            missing.append("请选择学硕或专硕")
        if missing:
            return {"outcome": "NEEDS_INPUT", "answer": "推荐条件尚不完整。", "followUp": missing,
                    "candidates": [], "unverifiedCandidates": []}
        accepted, excluded = [], []
        for p, doc in self.programs:
            reasons = []
            for mismatch, reason in ((p.year != profile.examYear, "年份不匹配"),
                (p.majorCode not in majors, "专业不匹配"), (p.degreeType != pref.degreeType, "学位类型不匹配"),
                (bool(pref.studyMode) and p.studyMode != pref.studyMode, "学习方式不匹配"),
                (bool(pref.examSubjects) and not set(pref.examSubjects) <= set(p.examSubjects), "考试科目不匹配"),
                (bool(pref.regions) and pref.regionConstraint == "required" and p.region not in pref.regions, "地区不匹配")):
                if mismatch:
                    reasons.append(reason)
            if reasons:
                excluded.append({"programId": p.programId, "school": p.school, "reasons": reasons})
                continue
            region_match = bool(pref.regions) and p.region in pref.regions
            candidate = p.model_dump()
            candidate.update(matchedConditions=["招生年份一致", "专业一致", "学位类型一致"]
                + (["地区偏好匹配"] if region_match else []),
                pendingChecks=["报考资格、方向及最新调整请核对招生章程；未据本科背景推定资格"],
                sourceIds=[doc.id], explanation="；".join(["招生年份、专业和学位类型符合条件"]
                    + (["地区符合偏好"] if region_match else [])))
            accepted.append((int(region_match), p.updatedAt, candidate, doc))
        # Stable tie breaks: preferred region, metadata completeness, update date, ID.
        accepted.sort(key=lambda row: row[2]["programId"])
        accepted.sort(key=lambda row: row[1], reverse=True)
        accepted.sort(key=lambda row: row[0], reverse=True)
        selected = accepted[:5]
        candidates = [row[2] for row in selected]
        result = {"outcome": "COMPLETED" if candidates else "UNSUPPORTED",
            "answer": "以下为满足条件的候选清单，不代表录取概率。" if candidates else "当前2027资料范围内没有符合条件的候选；未替换为往年数据。",
            "candidates": candidates, "unverifiedCandidates": [], "excluded": excluded,
            "references": [row[3].reference().model_dump() for row in selected], "explanationMode": "rules",
            "profileSnapshot": profile.model_dump(), "preferences": pref.model_dump(),
            "coverage": "南京审计大学、中国科学院大学计算机学院、中国传媒大学；2027年081200/085404"}
        if candidates and pref.explainWithAi and self.settings.LLM_ENABLED:
            try:
                answer = await self.model.generate(get("tuijian_yuanxiao"),
                    {"input": req.userInput, "messages": [m.model_dump() for m in req.messages],
                     "profile": profile.model_dump(), "candidates": candidates,
                     "sources": [{"id": row[3].id, "content": row[3].content} for row in selected]}, Explanations)
                mapping = {e.programId: e for e in answer.explanations}
                if len(mapping) != len(answer.explanations) or set(mapping) != {c["programId"] for c in candidates}:
                    raise ValueError("candidate_mismatch")
                for c in candidates:
                    if not set(mapping[c["programId"]].sourceIds) <= set(c["sourceIds"]):
                        raise ValueError("unknown_source")
                for c in candidates:
                    c["explanation"] = mapping[c["programId"]].text
                result["explanationMode"] = "ai"
            except Exception as e:
                log.warning("schoolModelFailure=%s", type(e).__name__)
                result.update(explanationMode="fallback", notice="AI解释不可用，规则候选及来源已保留。")
        return result

    async def tutor(self, req):
        attempt = req.attempt
        analysis = attempt.analysis or "此版本未保存解析，无法从已有解析解释原因。"
        result = {"outcome": "COMPLETED", "recordId": attempt.recordId,
            "standardAnswer": attempt.answer, "userAnswer": attempt.userAnswer, "questionVersion": attempt.version,
            "answer": f"你的选择：{attempt.userAnswer}；此版本标准答案：{attempt.answer}。\n原题解析：{analysis[:3500]}",
            "explanationMode": "rules", "notice": "未启用 AI，当前仅展示原题解析，尚未生成个性化解释或追问回答。"}
        if self.settings.LLM_ENABLED:
            try:
                output = await self.model.generate(get("wrong_question_tutor"),
                    {"attempt": attempt.model_dump(), "query": req.userInput,
                     "messages": [m.model_dump() for m in req.messages]}, TutorExplanation)
                # Revalidate even a custom provider adapter's output.
                output = TutorExplanation.model_validate(output.model_dump())
                if output.standardAnswer != attempt.answer:
                    raise ValueError("standard_answer_mismatch")
                result.update(answer=output.explanation, explanationMode="ai",
                    notice="AI 辅助解释可能有误，标准答案和判分以已保存作答为准。")
            except Exception as e:
                log.warning("tutorModelFailure=%s", type(e).__name__)
                result.update(explanationMode="fallback", notice="AI 解释或追问暂不可用，已保留原题解析，可稍后重试。")
        return result

    async def summary(self, req):
        if not req.questions:
            return {"outcome": "NEEDS_INPUT", "answer": "该批次尚无可总结的有效作答。"}
        correct = sum(q.correct for q in req.questions)
        total = len(req.questions)
        weak = sorted({q.knowledgePoint or q.subject for q in req.questions if not q.correct})
        result = {"outcome": "COMPLETED", "answer": f"有效作答{total}题，正确{correct}题。",
            "total": total, "correct": correct, "accuracy": round(correct / total * 100, 1),
            "weakPoints": weak, "explanationMode": "rules"}
        if self.settings.LLM_ENABLED:
            try:
                answer = await self.model.generate(get("practice_summary"),
                    {"statistics": result, "questions": [q.model_dump() for q in req.questions]}, Summary)
                result.update(answer=answer.summary, explanationMode="ai")
            except Exception as e:
                log.warning("summaryModelFailure=%s", type(e).__name__)
                result["explanationMode"] = "fallback"
        return result
