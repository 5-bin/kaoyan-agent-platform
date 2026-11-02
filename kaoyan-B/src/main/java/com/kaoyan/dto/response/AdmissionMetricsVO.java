package com.kaoyan.dto.response;

import java.util.List;

/** Source-backed catalog metrics; they do not authorize recommendations or RAG evidence. */
public record AdmissionMetricsVO(
        String college, String track, String studyMode, String admissionCategory,
        Metric enrollment, Metric cutoffReference) {

    public enum Status { OFFICIAL, UNVERIFIED, NOT_PUBLISHED, NOT_FOUND, SCOPE_MISMATCH, CONFLICT }
    public enum Basis { ORDINARY_EXAM, TOTAL_INCLUDING_RECOMMENDED, TOTAL_UNSPECIFIED, NOT_APPLICABLE }
    public enum SourceType { OFFICIAL, THIRD_PARTY }

    public record Source(String title, String url, String locator, String retrievedAt, SourceType sourceType) {}

    public record Metric(Integer year, Integer value, Status status, String scopeKey,
                         String scopeLabel, Basis basis, String notice, List<Source> sources) {}

    public record Context(String college, String track, String studyMode, String admissionCategory) {}
}
