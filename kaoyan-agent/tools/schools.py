"""Admission filtering and stable ranking as separate registered tools."""

from pydantic import Field

from retrieval import Document
from schemas import Preferences, Profile, StrictModel
from tools.registry import StrictToolRegistry, ValidatedTool


class Admission(StrictModel):
    """Validated admissions metadata from the active versioned corpus."""

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


class FilterParameters(StrictModel):
    """Only typed profile and preferences can influence filtering."""

    profile: Profile
    preferences: Preferences


class RankedCandidate(Admission):
    """Rule-generated candidate fields accepted at the ranking boundary."""

    matchedConditions: list[str]
    pendingChecks: list[str]
    sourceIds: list[str]
    explanation: str


class RankParameters(StrictModel):
    """Rows are produced by the trusted filter tool."""

    rows: list[tuple[int, str, RankedCandidate, Document]]


def school_tools(programs: list[tuple[Admission, Document]]) -> StrictToolRegistry:
    """Create request-local tools sharing only the immutable admissions copy."""

    def filter_programs(profile: dict, preferences: dict) -> dict:
        """Apply the existing hard constraints without model judgments."""
        profile = Profile.model_validate(profile)
        pref = Preferences.model_validate(preferences)
        majors = pref.majorCodes or []
        if not majors and profile.targetMajor:
            majors = sorted(
                {
                    p.majorCode
                    for p, _ in programs
                    if profile.targetMajor in {p.majorCode, p.major}
                }
            )
        accepted, excluded = ([], [])
        for p, doc in programs:
            reasons = []
            for mismatch, reason in (
                (p.year != profile.examYear, "年份不匹配"),
                (p.majorCode not in majors, "专业不匹配"),
                (p.degreeType != pref.degreeType, "学位类型不匹配"),
                (
                    bool(pref.studyMode) and p.studyMode != pref.studyMode,
                    "学习方式不匹配",
                ),
                (
                    bool(pref.examSubjects)
                    and (not set(pref.examSubjects) <= set(p.examSubjects)),
                    "考试科目不匹配",
                ),
                (
                    bool(pref.regions)
                    and pref.regionConstraint == "required"
                    and (p.region not in pref.regions),
                    "地区不匹配",
                ),
            ):
                if mismatch:
                    reasons.append(reason)
            if reasons:
                excluded.append(
                    {"programId": p.programId, "school": p.school, "reasons": reasons}
                )
                continue
            region_match = bool(pref.regions) and p.region in pref.regions
            candidate = p.model_dump()
            candidate.update(
                matchedConditions=["招生年份一致", "专业一致", "学位类型一致"]
                + (["地区偏好匹配"] if region_match else []),
                pendingChecks=[
                    "报考资格、方向及最新调整请核对招生章程；未据本科背景推定资格"
                ],
                sourceIds=[doc.id],
                explanation="；".join(
                    ["招生年份、专业和学位类型符合条件"]
                    + (["地区符合偏好"] if region_match else [])
                ),
            )
            accepted.append((int(region_match), p.updatedAt, candidate, doc))
        return {"accepted": accepted, "excluded": excluded}

    def rank_programs(rows: list) -> list:
        """Preserve region, date and ID tie breaks exactly."""
        rows.sort(key=lambda row: row[2]["programId"])
        rows.sort(key=lambda row: row[1], reverse=True)
        rows.sort(key=lambda row: row[0], reverse=True)
        return rows[:5]

    def decode(rows: list) -> list:
        """Restore only validated source documents."""
        return [
            (row[0], row[1], row[2], Document.model_validate(row[3])) for row in rows
        ]

    registry = StrictToolRegistry()
    registry.add(
        ValidatedTool(
            "filter_programs",
            "按年份、专业、学位及硬条件筛选院校",
            FilterParameters,
            filter_programs,
        )
    )
    registry.add(
        ValidatedTool(
            "rank_programs",
            "对规则候选稳定排序，最多5项",
            RankParameters,
            rank_programs,
            decode,
        )
    )
    return registry
