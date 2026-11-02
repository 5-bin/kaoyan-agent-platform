package com.kaoyan;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.service.SchoolService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.url=jdbc:h2:mem:school-metrics;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER,YEAR",
    "spring.datasource.username=sa", "spring.datasource.password=",
    "spring.sql.init.mode=always",
    "spring.sql.init.schema-locations=classpath:schema-test.sql,classpath:schema-school-test.sql,classpath:schema-school-metrics-test.sql",
    "jwt.secret=test-only-jwt-key-at-least-32-characters",
    "kaoyan.agent.internal-key=test-only-internal-key-12345"
})
@AutoConfigureMockMvc
@Transactional
class SchoolAdmissionMetricsTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @Autowired JdbcTemplate jdbc;
    @Autowired SchoolService schools;
    @MockitoBean StringRedisTemplate redis;

    private String login() throws Exception {
        String body = mapper.writeValueAsString(Map.of("username", "m" + UUID.randomUUID().toString().substring(0, 8),
                "password", "test-password"));
        mvc.perform(post("/api/auth/register").contentType("application/json").content(body)).andExpect(status().isOk());
        return mapper.readTree(mvc.perform(post("/api/auth/login").contentType("application/json").content(body))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString())
                .path("data").path("accessToken").asText();
    }

    private void seed() {
        jdbc.update("INSERT INTO school(id,name,province,level) VALUES(1,'指标测试校','河北','普通本科'),(2,'另一校','江苏','211')");
        jdbc.update("INSERT INTO school_detail(id,school_id,major_name,major_code,year,remark) VALUES"
                + "(10,1,'计算机科学与技术','081200',2027,'原备注'),(11,1,'计算机科学与技术','081200',2027,'另一方向'),"
                + "(20,2,'计算机科学与技术','081200',2027,'另一校')");
    }

    private void metric(int id, String type, int year, Integer value, String state, String sourceType, String url) throws Exception {
        String context = mapper.writeValueAsString(Map.of("college", "计算机学院", "track", "01计算机系统", "studyMode", "full_time", "admissionCategory", "ordinary"));
        String sources = mapper.writeValueAsString(List.of(Map.of("title", "测试来源", "url", url,
                "locator", "普通全日制专业合计，各方向共用", "retrievedAt", "2026-10-30", "sourceType", sourceType)));
        jdbc.update("INSERT INTO school_admission_metric(school_detail_id,metric_type,metric_year,metric_value,status,"
                        + "scope_key,scope_label,basis,context_json,sources_json,notice,content_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                id, type, year, value, state, "a".repeat(64), "专业合计，各方向共用",
                type.equals("ENROLLMENT") ? "TOTAL_INCLUDING_RECOMMENDED" : "NOT_APPLICABLE", context, sources, "仅供参考", "b".repeat(64));
    }

    @Test void historicalYearAndScopeAreExplicitAndLegacyColumnsRemainNull() throws Exception {
        seed();
        metric(10, "ENROLLMENT", 2027, 80, "OFFICIAL", "OFFICIAL", "https://example.edu.cn/plan");
        metric(10, "CUTOFF_REFERENCE", 2026, 310, "OFFICIAL", "OFFICIAL", "https://example.edu.cn/cutoff");
        String response = mvc.perform(get("/api/schools/1").header("Authorization", "Bearer " + login()))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        var row = mapper.readTree(response).path("data").path("details").findValue("admissionMetrics");
        org.junit.jupiter.api.Assertions.assertEquals(2026, row.path("cutoffReference").path("year").asInt());
        org.junit.jupiter.api.Assertions.assertEquals(80, row.path("enrollment").path("value").asInt());
        org.junit.jupiter.api.Assertions.assertEquals("TOTAL_INCLUDING_RECOMMENDED", row.path("enrollment").path("basis").asText());
        org.junit.jupiter.api.Assertions.assertNull(jdbc.queryForObject("SELECT score_line FROM school_detail WHERE id=10", Integer.class));
        org.junit.jupiter.api.Assertions.assertNull(jdbc.queryForObject("SELECT enrollment_count FROM school_detail WHERE id=10", Integer.class));
    }

    @Test void thirdPartyDataRemainUnverifiedAndDoNotLeakToOtherSchools() throws Exception {
        seed();
        metric(10, "CUTOFF_REFERENCE", 2026, 300, "UNVERIFIED", "THIRD_PARTY", "https://example.org/cutoff");
        String token = login();
        mvc.perform(get("/api/schools/1").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.details[?(@.id == 10)].admissionMetrics.cutoffReference.status").value("UNVERIFIED"));
        mvc.perform(get("/api/schools/2").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.details[0].admissionMetrics").doesNotExist());
        mvc.perform(get("/api/schools/1")).andExpect(status().isUnauthorized());
    }

    @Test void sameYearCutoffAndWrongYearEnrollmentAreRejected() throws Exception {
        seed();
        metric(10, "CUTOFF_REFERENCE", 2027, 300, "OFFICIAL", "OFFICIAL", "https://example.edu.cn/cutoff");
        assertFalse(((List<?>) schools.detail(1L).get("warnings")).isEmpty());
        jdbc.update("DELETE FROM school_admission_metric");
        metric(10, "ENROLLMENT", 2026, 80, "OFFICIAL", "OFFICIAL", "https://example.edu.cn/plan");
        assertFalse(((List<?>) schools.detail(1L).get("warnings")).isEmpty());
    }

    @Test void untrustedEvidenceCannotBePresentedAsOfficialOrExecutableLinks() throws Exception {
        seed();
        metric(10, "CUTOFF_REFERENCE", 2026, 300, "OFFICIAL", "THIRD_PARTY", "https://example.org/cutoff");
        assertFalse(((List<?>) schools.detail(1L).get("warnings")).isEmpty());
        jdbc.update("DELETE FROM school_admission_metric");
        metric(10, "CUTOFF_REFERENCE", 2026, 300, "UNVERIFIED", "THIRD_PARTY", "javascript:alert(1)");
        assertFalse(((List<?>) schools.detail(1L).get("warnings")).isEmpty());
    }

    @Test void conflictsRemainNullInsteadOfChoosingAnArbitraryScore() throws Exception {
        seed();
        metric(10, "CUTOFF_REFERENCE", 2026, null, "CONFLICT", "THIRD_PARTY", "https://example.org/conflict");
        mvc.perform(get("/api/schools/1").header("Authorization", "Bearer " + login()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.details[?(@.id == 10)].admissionMetrics.cutoffReference.status").value("CONFLICT"));
    }

    @Test void invalidMetricDoesNotHideAnotherValidMetricOrExposeLegacyNumber() throws Exception {
        seed();
        jdbc.update("UPDATE school_detail SET score_line=999 WHERE id=10");
        metric(10, "CUTOFF_REFERENCE", 2027, 300, "OFFICIAL", "OFFICIAL", "https://example.edu.cn/cutoff");
        metric(10, "ENROLLMENT", 2027, 80, "OFFICIAL", "OFFICIAL", "https://example.edu.cn/plan");
        mvc.perform(get("/api/schools/1").header("Authorization", "Bearer " + login()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.school.name").value("指标测试校"))
                .andExpect(jsonPath("$.data.warnings[0].code").value("INVALID_METRIC"))
                .andExpect(jsonPath("$.data.details[?(@.id == 10)].admissionMetrics.enrollment.value").value(80))
                .andExpect(jsonPath("$.data.details[?(@.id == 10)].scoreLine").value(org.hamcrest.Matchers.contains((Object) null)));
        assertEquals(999, jdbc.queryForObject("SELECT score_line FROM school_detail WHERE id=10", Integer.class));
    }
}
