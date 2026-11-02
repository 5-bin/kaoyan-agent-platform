"""Typed, offline validation and selection for catalog-only admission metrics.

This is a maintenance module, not an Agent and not a runtime database client.
Source text is untrusted data and never executed. Years and scopes must match
before a numeric observation can be selected for a catalog row.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

MetricType = Literal["ENROLLMENT", "CUTOFF_REFERENCE"]
Status = Literal["OFFICIAL", "UNVERIFIED", "NOT_PUBLISHED", "NOT_FOUND", "SCOPE_MISMATCH", "CONFLICT"]
Basis = Literal["ORDINARY_EXAM", "TOTAL_INCLUDING_RECOMMENDED", "TOTAL_UNSPECIFIED", "NOT_APPLICABLE"]
SourceType = Literal["OFFICIAL", "THIRD_PARTY"]


class StrictModel(BaseModel):
    """Reject unknown input fields rather than silently discarding scope facts."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Source(StrictModel):
    """A public source location; no credentials, HTML, or private context."""

    title: str = Field(min_length=1, max_length=500)
    url: str = Field(max_length=2000)
    locator: str = Field(min_length=1, max_length=2000)
    retrieved_at: date = Field(alias="retrievedAt")
    source_type: SourceType = Field(alias="sourceType")

    @model_validator(mode="after")
    def check_source(self) -> Self:
        """Require an HTTPS public hostname, no credentials, and a real retrieval date."""
        parts = urlsplit(self.url)
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or parts.hostname in ("localhost", "127.0.0.1", "::1")
                or self.retrieved_at > date.today()):
            raise ValueError("来源必须为无凭证HTTPS公开网址，获取日期不得在未来")
        return self


class Context(StrictModel):
    """The row's original college, track, study mode and admission category."""

    college: str = Field(max_length=255)
    track: str = Field(max_length=1000)
    study_mode: str = Field(alias="studyMode", max_length=50)
    admission_category: str = Field(alias="admissionCategory", max_length=50)


class Target(StrictModel):
    """Unambiguous business-row identity, restored from original collection mappings."""

    detail_id: StrictInt = Field(alias="detailId", gt=0)
    school_id: StrictInt = Field(alias="schoolId", gt=0)
    school: str
    major_code: str = Field(alias="majorCode", pattern=r"^\d{6}$")
    year: StrictInt
    context: Context


class Observation(StrictModel):
    """A reviewed observation with its own year and exact applicable scope.

    track='*' means an explicitly shared professional plan/line, never an
    allocation to each direction. A college rename requires an explicit
    match in the prepared observation rather than fuzzy string matching.
    """

    school_id: StrictInt = Field(alias="schoolId", gt=0)
    college: str
    major_code: str = Field(alias="majorCode", pattern=r"^\d{6}$")
    study_mode: str = Field(alias="studyMode")
    admission_category: str = Field(alias="admissionCategory")
    track: str = "*"
    metric_type: MetricType = Field(alias="metricType")
    year: StrictInt
    value: StrictInt = Field(ge=0, le=100000)
    basis: Basis
    scope_label: str = Field(alias="scopeLabel", min_length=1, max_length=500)
    notice: str = Field(default="", max_length=2000)
    source: Source

    @model_validator(mode="after")
    def check_metric(self) -> Self:
        """Prevent totals/means, future cutoffs and non-total score scales."""
        if self.metric_type == "CUTOFF_REFERENCE":
            if self.year > date.today().year or self.value > 500 or self.basis != "NOT_APPLICABLE":
                raise ValueError("复试参考线必须为已公布年度、500分制总分")
        elif self.basis == "NOT_APPLICABLE":
            raise ValueError("招生计划必须说明人数口径")
        return self


class Metric(StrictModel):
    """Selected numeric value or explicit evidence gap for one target row."""

    year: StrictInt | None
    value: StrictInt | None
    status: Status
    scope_key: str = Field(alias="scopeKey", pattern=r"^[a-f0-9]{64}$")
    scope_label: str = Field(alias="scopeLabel", max_length=500)
    basis: Basis
    notice: str = Field(max_length=2000)
    sources: list[Source]

    @model_validator(mode="after")
    def check_evidence(self) -> Self:
        """Require evidence for numeric facts and forbid invented gap values."""
        numeric = self.status in ("OFFICIAL", "UNVERIFIED")
        if numeric != (self.value is not None):
            raise ValueError("缺口或冲突不得携带确定数值")
        if numeric and (self.year is None or not self.sources or self.value < 0):
            raise ValueError("数值必须有年份和来源")
        if self.status == "OFFICIAL" and any(s.source_type != "OFFICIAL" for s in self.sources):
            raise ValueError("第三方数据不得提升为官方事实")
        return self


class Entry(StrictModel):
    """A validated target plus its two catalog projections."""

    target: Target
    enrollment: Metric
    cutoff_reference: Metric = Field(alias="cutoffReference")

    @model_validator(mode="after")
    def check_years(self) -> Self:
        """An enrollment belongs to its target year; a reference cutoff is historical."""
        if self.enrollment.year not in (None, self.target.year):
            raise ValueError("招生计划不得跨年回填")
        year = self.cutoff_reference.year
        if year is not None and (year >= self.target.year or year > date.today().year):
            raise ValueError("历史线不得冒充目标年度复试线")
        if self.cutoff_reference.basis != "NOT_APPLICABLE":
            raise ValueError("复试线不适用人数口径")
        return self


class SchoolChange(StrictModel):
    """Verified classification and the exact old value protected by import guards."""

    school_id: StrictInt = Field(alias="schoolId", gt=0)
    name: str
    old_level: str | None = Field(alias="oldLevel")
    level: Literal["985", "211", "双一流", "普通本科"]
    evidence_note: str = Field(alias="evidenceNote")
    sources: list[Source] = Field(min_length=1)


class Manifest(StrictModel):
    """Complete, checksummed import plan; excludes all private user tables."""

    format: Literal["school-metrics-v1"]
    database: Literal["kaoyan_dev"]
    checked_at: date = Field(alias="checkedAt")
    workbook_sha256: str = Field(alias="workbookSha256", pattern=r"^[a-f0-9]{64}$")
    catalog_fingerprints: dict[str, list[str]] = Field(alias="catalogFingerprints")
    schools: list[SchoolChange]
    entries: list[Entry]
    research: dict[str, list[str]]
    manifest_sha256: str = Field(alias="manifestSha256", pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def check_integrity(self) -> Self:
        """Reject tampering, duplicate IDs and scope values that would be double counted."""
        data = self.model_dump(mode="json", by_alias=True, exclude={"manifest_sha256"})
        if digest(data) != self.manifest_sha256:
            raise ValueError("导入清单校验和不符")
        if set(self.catalog_fingerprints) != {"school", "school_detail", "collection_import_record"}:
            raise ValueError("原始行保护范围不符")
        if len({s.school_id for s in self.schools}) != len(self.schools):
            raise ValueError("院校ID重复")
        if len({e.target.detail_id for e in self.entries}) != len(self.entries):
            raise ValueError("专业ID重复")
        shared: dict[str, tuple[int | None, int | None, str]] = {}
        school_ids = {s.school_id for s in self.schools}
        for entry in self.entries:
            if entry.target.school_id not in school_ids:
                raise ValueError("专业院校不在本轮清单")
            for metric in (entry.enrollment, entry.cutoff_reference):
                value = (metric.year, metric.value, metric.basis)
                if metric.scope_key in shared and shared[metric.scope_key] != value:
                    raise ValueError("共享范围的指标数值冲突")
                shared[metric.scope_key] = value
        return self


def canonical(value: object) -> str:
    """Serialize JSON deterministically for evidence and optimistic write guards."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: object) -> str:
    """Return the SHA-256 of canonical UTF-8 JSON."""
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def select_metric(target: Target, kind: MetricType, observations: list[Observation],
                  searched_sources: list[Source]) -> Metric:
    """Select official-first exact-scope evidence, retaining same-priority conflicts.

    Official matching data outranks third parties; within each source tier the
    latest historical year wins, and ordinary exam seats outrank total plans.
    Broader or different-college facts remain gaps rather than guessed matches.
    """
    eligible = [o for o in observations if o.metric_type == kind and o.school_id == target.school_id
                and o.major_code == target.major_code and o.college == target.context.college
                and o.study_mode == target.context.study_mode
                and o.admission_category == target.context.admission_category
                and o.track in ("*", target.context.track)
                and (o.year == target.year if kind == "ENROLLMENT" else o.year < target.year)]
    scope = [target.school_id, target.major_code, target.context.model_dump(), kind, target.year]
    if not eligible:
        near = [o for o in observations if o.metric_type == kind and o.school_id == target.school_id
                and o.major_code == target.major_code]
        return Metric(year=target.year if kind == "ENROLLMENT" else None, value=None,
                      status="SCOPE_MISMATCH" if near else "NOT_FOUND", scopeKey=digest(scope),
                      scopeLabel="本专业原登记学院、学习方式及招考类别", basis="NOT_APPLICABLE",
                      notice="已查到相关指标，但年份、学院、学习方式或招考类别不匹配；不跨范围回填。" if near else
                      "已完成本轮公开来源检索，未取得本专业同范围的可靠数值；不代表学校未招生或未公布。",
                      sources=([o.source for o in near] or searched_sources)[:5])
    def priority(observation: Observation) -> tuple[int, int, int, int]:
        return (0 if observation.source.source_type == "OFFICIAL" else 1,
                -observation.year, 0 if observation.track != "*" else 1,
                {"ORDINARY_EXAM": 0, "TOTAL_INCLUDING_RECOMMENDED": 1,
                 "TOTAL_UNSPECIFIED": 2, "NOT_APPLICABLE": 0}[observation.basis])
    first = min(eligible, key=priority)
    chosen = [o for o in eligible if priority(o) == priority(first)]
    conflict = len({o.value for o in chosen}) > 1
    scope = [first.school_id, first.college, first.major_code, first.study_mode,
             first.admission_category, first.track, kind, first.year, first.basis]
    sources = list({canonical(o.source.model_dump(mode="json", by_alias=True)): o.source for o in chosen}.values())
    return Metric(year=first.year, value=None if conflict else first.value,
                  status="CONFLICT" if conflict else "OFFICIAL" if first.source.source_type == "OFFICIAL" else "UNVERIFIED",
                  scopeKey=digest(scope), scopeLabel=first.scope_label, basis=first.basis,
                  notice="同优先级来源存在冲突，未选取确定数值；逐项登记值见来源定位。" if conflict else first.notice,
                  sources=sources)


def load_manifest(path: Path) -> Manifest:
    """Read and validate a prepared plan without connecting to any database."""
    return Manifest.model_validate_json(path.read_text(encoding="utf-8"))


def database_values(entry: Entry, kind: MetricType) -> dict[str, object]:
    """Build only the V14 columns; never produce SQL for legacy score fields."""
    metric = entry.enrollment if kind == "ENROLLMENT" else entry.cutoff_reference
    values: dict[str, object] = {
        "school_detail_id": entry.target.detail_id, "metric_type": kind,
        "metric_year": metric.year, "metric_value": metric.value, "status": metric.status,
        "scope_key": metric.scope_key, "scope_label": metric.scope_label, "basis": metric.basis,
        "context_json": canonical(entry.target.context.model_dump(mode="json", by_alias=True)),
        "sources_json": canonical([s.model_dump(mode="json", by_alias=True) for s in metric.sources]),
        "notice": metric.notice,
    }
    values["content_sha256"] = digest(values)
    return values
