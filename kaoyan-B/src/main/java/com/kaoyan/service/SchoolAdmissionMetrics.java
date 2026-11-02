package com.kaoyan.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.dto.response.AdmissionMetricsVO;
import com.kaoyan.dto.response.AdmissionMetricsVO.Basis;
import com.kaoyan.dto.response.AdmissionMetricsVO.Context;
import com.kaoyan.dto.response.AdmissionMetricsVO.Metric;
import com.kaoyan.dto.response.AdmissionMetricsVO.Source;
import com.kaoyan.dto.response.AdmissionMetricsVO.Status;
import com.kaoyan.entity.SchoolDetail;
import com.kaoyan.dto.response.SchoolWarning;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.BadSqlGrammarException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Reads catalog-only metrics; an older database without V14 retains its original response. */
@Service
@RequiredArgsConstructor
public class SchoolAdmissionMetrics {
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;

    public List<SchoolWarning> enrich(List<SchoolDetail> details) {
        List<SchoolWarning> warnings = new ArrayList<>();
        if (details.isEmpty()) {
            return warnings;
        }
        Map<Long, SchoolDetail> byId = new HashMap<>();
        details.forEach(detail -> byId.put(detail.getId(), detail));
        String placeholders = String.join(",", java.util.Collections.nCopies(details.size(), "?"));
        Map<Long, List<StoredMetric>> rows = new HashMap<>();
        try {
            jdbc.query("SELECT * FROM school_admission_metric WHERE school_detail_id IN (" + placeholders + ")",
                (org.springframework.jdbc.core.RowCallbackHandler) result -> {
                    long id = result.getLong("school_detail_id");
                    String type = result.getString("metric_type");
                    try {
                        StoredMetric stored = read(result, byId.get(id));
                        rows.computeIfAbsent(id, ignored -> new ArrayList<>()).add(stored);
                    } catch (IllegalStateException exception) {
                        hideLegacy(byId.get(id), type);
                        warnings.add(new SchoolWarning("INVALID_METRIC", id, type,
                                "该指标未通过年份、口径或来源校验，已隐藏，请查阅官网确认。"));
                    }
                }, details.stream().map(SchoolDetail::getId).toArray());
        } catch (BadSqlGrammarException exception) {
            SQLException sql = exception.getSQLException();
            if ("42S02".equals(sql.getSQLState()) || sql.getErrorCode() == 1146
                    || sql.getErrorCode() == 42102 || sql.getErrorCode() == 42104) {
                return warnings; // V14 is optional; other SQL failures must propagate.
            }
            throw exception;
        }
        rows.forEach((id, items) -> {
            Context context = items.get(0).context();
            if (items.stream().anyMatch(item -> !context.equals(item.context()))) {
                hideLegacy(byId.get(id), "ENROLLMENT");
                hideLegacy(byId.get(id), "CUTOFF_REFERENCE");
                warnings.add(new SchoolWarning("METRIC_CONTEXT_CONFLICT", id, null,
                        "招生指标的学院或方向口径不一致，已隐藏该专业指标，请查阅官网确认。"));
                return;
            }
            Metric enrollment = items.stream().filter(item -> item.type().equals("ENROLLMENT"))
                    .map(StoredMetric::metric).findFirst().orElse(null);
            Metric cutoff = items.stream().filter(item -> item.type().equals("CUTOFF_REFERENCE"))
                    .map(StoredMetric::metric).findFirst().orElse(null);
            byId.get(id).setAdmissionMetrics(new AdmissionMetricsVO(context.college(), context.track(),
                    context.studyMode(), context.admissionCategory(), enrollment, cutoff));
        });
        return warnings;
    }

    private void hideLegacy(SchoolDetail detail, String type) {
        if ("ENROLLMENT".equals(type)) detail.setEnrollmentCount(null);
        else if ("CUTOFF_REFERENCE".equals(type)) detail.setScoreLine(null);
        else {
            detail.setEnrollmentCount(null);
            detail.setScoreLine(null);
        }
    }

    private StoredMetric read(ResultSet result, SchoolDetail detail) throws SQLException {
        try {
            String type = result.getString("metric_type");
            Integer year = result.getObject("metric_year", Integer.class);
            Integer value = result.getObject("metric_value", Integer.class);
            Status status = Status.valueOf(result.getString("status"));
            Basis basis = Basis.valueOf(result.getString("basis"));
            boolean hasValue = status == Status.OFFICIAL || status == Status.UNVERIFIED;
            if (!(type.equals("ENROLLMENT") || type.equals("CUTOFF_REFERENCE"))
                    || hasValue != (value != null)
                    || (hasValue && (year == null || value < 0))
                    || (year != null && (detail.getYear() == null
                        || (type.equals("ENROLLMENT") ? !year.equals(detail.getYear())
                            : year >= detail.getYear() || year > LocalDate.now().getYear())))
                    || (type.equals("CUTOFF_REFERENCE") && basis != Basis.NOT_APPLICABLE)) {
                throw new IllegalStateException("院校指标年份或口径无效");
            }
            List<Source> sources = mapper.readValue(result.getString("sources_json"), new TypeReference<>() {});
            if (sources == null) throw new IllegalStateException("院校指标证据无效");
            for (Source source : sources) {
                if (source == null || source.url() == null || source.retrievedAt() == null)
                    throw new IllegalStateException("院校指标证据无效");
                URI uri = URI.create(source.url());
                if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
                        || uri.getUserInfo() != null || source.sourceType() == null
                        || LocalDate.parse(source.retrievedAt()).isAfter(LocalDate.now())) {
                    throw new IllegalStateException("院校指标来源无效");
                }
            }
            if (hasValue && (sources.isEmpty() || (status == Status.OFFICIAL && sources.stream()
                    .anyMatch(source -> source.sourceType() != AdmissionMetricsVO.SourceType.OFFICIAL)))) {
                throw new IllegalStateException("院校指标证据缺失");
            }
            Context context = mapper.readValue(result.getString("context_json"), Context.class);
            if (context == null) throw new IllegalStateException("院校指标口径无效");
            Metric metric = new Metric(year, value, status, result.getString("scope_key"),
                    result.getString("scope_label"), basis, result.getString("notice"), List.copyOf(sources));
            return new StoredMetric(type, context, metric);
        } catch (JsonProcessingException | IllegalArgumentException | java.time.DateTimeException exception) {
            throw new IllegalStateException("院校指标记录无效");
        }
    }

    private record StoredMetric(String type, Context context, Metric metric) {}
}
