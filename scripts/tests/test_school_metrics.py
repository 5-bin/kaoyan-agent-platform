"""Regression checks for year, scope, provenance and safe idempotent imports."""
import importlib.util
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from school_metrics import Context, Entry, Metric, Observation, Source, Target, database_values, digest, select_metric


def target(**changes):
    """Create an isolated scope; no real school facts are asserted by these tests."""
    values = dict(detailId=1, schoolId=1, school="测试校", majorCode="081200", year=2027,
                  context=Context(college="计算机学院", track="01方向", studyMode="full_time", admissionCategory="ordinary"))
    values.update(changes)
    return Target(**values)


def observation(**changes):
    """Create source-backed synthetic observations with explicit dimensions."""
    values = dict(schoolId=1, college="计算机学院", majorCode="081200", studyMode="full_time",
                  admissionCategory="ordinary", track="*", metricType="ENROLLMENT", year=2027,
                  value=40, basis="ORDINARY_EXAM", scopeLabel="专业合计，各方向共用", notice="暂定计划",
                  source=Source(title="测试目录", url="https://example.edu.cn/plan", locator="专业合计40人",
                                retrievedAt="2026-10-30", sourceType="OFFICIAL"))
    values.update(changes)
    return Observation(**values)


@pytest.mark.parametrize("field,value", [("schoolId", 2), ("college", "软件学院"), ("majorCode", "085404"),
                                        ("studyMode", "part_time"), ("admissionCategory", "special"), ("track", "02方向"), ("year", 2026)])
def test_unmatched_scope_or_year_never_supplies_an_enrollment(field, value):
    result = select_metric(target(), "ENROLLMENT", [observation(**{field: value})], [])
    assert result.value is None
    assert result.status in ("NOT_FOUND", "SCOPE_MISMATCH")


def test_shared_plan_retains_one_scope_key_and_is_not_allocated():
    first = select_metric(target(), "ENROLLMENT", [observation()], [])
    other = target(detailId=2, context=Context(college="计算机学院", track="02方向", studyMode="full_time", admissionCategory="ordinary"))
    second = select_metric(other, "ENROLLMENT", [observation()], [])
    assert first.value == second.value == 40
    assert first.scope_key == second.scope_key
    assert "共用" in first.scope_label


def test_official_sources_and_ordinary_seats_take_priority_without_subtracting_recommended_seats():
    official_total = observation(value=100, basis="TOTAL_INCLUDING_RECOMMENDED")
    ordinary = observation(value=40)
    third = observation(value=99, source=observation().source.model_copy(update={"source_type": "THIRD_PARTY"}))
    assert select_metric(target(), "ENROLLMENT", [official_total, third, ordinary], []).value == 40
    assert select_metric(target(), "ENROLLMENT", [official_total, third], []).value == 100


def test_third_party_fallback_is_explicit_and_conflicts_keep_all_sources():
    one = observation(value=39, source=Source(title="第三方甲", url="https://example.org/a", locator="登记39人",
                                            retrievedAt="2026-10-30", sourceType="THIRD_PARTY"))
    two = observation(value=41, source=Source(title="第三方乙", url="https://example.org/b", locator="登记41人",
                                            retrievedAt="2026-10-30", sourceType="THIRD_PARTY"))
    assert select_metric(target(), "ENROLLMENT", [one], []).status == "UNVERIFIED"
    conflict = select_metric(target(), "ENROLLMENT", [one, two], [])
    assert conflict.status == "CONFLICT" and conflict.value is None
    assert len(conflict.sources) == 2


def test_latest_official_historical_line_has_its_own_year():
    old = observation(metricType="CUTOFF_REFERENCE", year=2025, value=290, basis="NOT_APPLICABLE")
    recent = observation(metricType="CUTOFF_REFERENCE", year=2026, value=300, basis="NOT_APPLICABLE")
    result = select_metric(target(), "CUTOFF_REFERENCE", [old, recent], [])
    assert (result.year, result.value) == (2026, 300)
    entry = Entry(target=target(), enrollment=select_metric(target(), "ENROLLMENT", [], []), cutoffReference=result)
    columns = database_values(entry, "CUTOFF_REFERENCE")
    assert columns["metric_year"] == 2026
    assert "score_line" not in columns and "enrollment_count" not in columns


def test_cross_year_plan_and_future_reference_are_rejected_by_manifest_entries():
    plan = select_metric(target(), "ENROLLMENT", [observation()], [])
    line = select_metric(target(), "CUTOFF_REFERENCE", [], [])
    with pytest.raises(ValidationError, match="跨年"):
        Entry(target=target(), enrollment=plan.model_copy(update={"year": 2026}), cutoffReference=line)
    with pytest.raises(ValidationError, match="历史线"):
        Entry(target=target(), enrollment=plan, cutoffReference=line.model_copy(update={"year": 2027}))


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://user:secret@example.org/a", "http://example.org/a", "https://localhost/a"])
def test_source_urls_are_data_and_cannot_carry_scripts_or_credentials(url):
    with pytest.raises(ValidationError):
        Source(title="来源", url=url, locator="定位", retrievedAt="2026-10-30", sourceType="THIRD_PARTY")


def test_missing_values_cannot_be_filled_with_zero_or_promoted_to_official():
    metric = select_metric(target(), "ENROLLMENT", [], [])
    assert metric.value is None
    with pytest.raises(ValidationError):
        Metric.model_validate({**metric.model_dump(by_alias=True), "value": 0})
    third = Source(title="第三方", url="https://example.org/a", locator="40人", retrievedAt="2026-10-30", sourceType="THIRD_PARTY")
    with pytest.raises(ValidationError, match="提升"):
        Metric(year=2027, value=40, status="OFFICIAL", scopeKey=digest("scope"), scopeLabel="合计",
               basis="ORDINARY_EXAM", notice="", sources=[third])


def test_importer_preserves_modified_metrics_and_sql_is_not_interpolated():
    spec = importlib.util.spec_from_file_location("metrics_import_test", ROOT / "scripts/import-school-metrics.py")
    importer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(importer)
    row = {"school_detail_id": 1, "metric_type": "ENROLLMENT", "context_json": {"college": "学院"},
           "sources_json": [], "imported_at": "timestamp"}
    assert importer.normalize_saved(row)["context_json"] == '{"college":"学院"}'
    assert "imported_at" not in importer.normalize_saved(row)
    payload = "'); DELETE FROM user; -- $(cat .env) `whoami`"
    assert payload not in importer.sql(payload)
    assert importer.sql(payload).startswith("CONVERT(0x")
