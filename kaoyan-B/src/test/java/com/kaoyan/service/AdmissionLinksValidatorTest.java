package com.kaoyan.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class AdmissionLinksValidatorTest {
    private final ObjectMapper json = new ObjectMapper();

    private Map<String, Object> query(String code) {
        return new LinkedHashMap<>(Map.of("schoolCode", code));
    }

    private Map<String, Object> plan() {
        return new LinkedHashMap<>(Map.of(
            "action", "ADMISSION_LINKS", "admissionLinks", query("nau"),
            "operation", "NONE", "reads", List.of()));
    }

    private Map<String, Object> links() {
        return new LinkedHashMap<>(Map.of(
            "schoolCode", "nau",
            "schoolName", "南京审计大学",
            "registeredYear", 2027,
            "entryUrls", List.of(
                "https://gs.nau.edu.cn/2026/0920/c4397a161925/page.htm",
                "https://gs.nau.edu.cn/")));
    }

    private Map<String, Object> output() {
        return new LinkedHashMap<>(Map.of("admissionLinks", links(), "references", List.of()));
    }

    @Test void acceptsOnlyExplicitCurrentExamplesAndOldResultsWithoutCheck() {
        for (String text : List.of("查官网南京审计大学", "南京审计大学查官网",
            "帮我查询北京航空航天大学招生信息", "给我南京审计大学招生网址", "核对南京审计大学招生信息")) {
            Map<String, Object> value = plan();
            if (text.contains("北京航空航天大学")) value.put("admissionLinks", query("buaa"));
            assertDoesNotThrow(() -> AdmissionLinksValidator.validatePlan(value, text), text);
        }
        assertDoesNotThrow(() -> AdmissionLinksValidator.validateResult(Map.of(), Map.of("action", "CHAT"), "old"));
        assertDoesNotThrow(() -> AdmissionLinksValidator.validateResult(Map.of("outcome", "UNSUPPORTED"), plan(), "old"));
        assertDoesNotThrow(() -> AdmissionLinksValidator.validateResult(output(), plan(), "rag-v1-0000000000000000"));
    }

    @Test void refusesUnrequestedLookupsOldActionsAndUnknownFields() {
        assertFalse(AdmissionLinksValidator.requested("推荐南京审计大学"));
        assertFalse(AdmissionLinksValidator.requested("不要查官网南京审计大学"));
        assertFalse(AdmissionLinksValidator.requested("示例：查询南京审计大学招生信息"));
        assertFalse(AdmissionLinksValidator.requested("如何使用查官网功能"));
        assertFalse(AdmissionLinksValidator.requested("你可以查询哪些学校官网"));
        assertThrows(IllegalStateException.class, () -> AdmissionLinksValidator.validatePlan(plan(), "推荐南京审计大学"));
        assertThrows(IllegalStateException.class, () -> AdmissionLinksValidator.validatePlan(plan(), "不要查官网南京审计大学"));
        var old = plan();
        old.put("action", "ADMISSION_CHECK");
        old.put("admissionCheck", query("nau"));
        old.remove("admissionLinks");
        assertThrows(IllegalStateException.class, () -> AdmissionLinksValidator.validatePlan(old, "查官网南京审计大学"));
        var extra = plan();
        ((Map<String, Object>) extra.get("admissionLinks")).put("year", 2027);
        assertThrows(IllegalStateException.class, () -> AdmissionLinksValidator.validatePlan(extra, "查官网南京审计大学"));
        var reads = plan();
        reads.put("reads", List.of("documents"));
        assertThrows(IllegalStateException.class, () -> AdmissionLinksValidator.validatePlan(reads, "查官网南京审计大学"));
        var operation = plan();
        operation.put("operation", "PRACTICE_CREATE");
        assertThrows(IllegalStateException.class, () -> AdmissionLinksValidator.validatePlan(operation, "查官网南京审计大学"));
        var steps = plan();
        steps.put("steps", List.of(Map.of("agent", "SCHOOL", "dependsOn", List.of())));
        assertThrows(IllegalStateException.class, () -> AdmissionLinksValidator.validatePlan(steps, "查官网南京审计大学"));
    }

    @Test void missingMultipleAndUnknownSchoolsRemainClarifications() {
        for (String text : List.of("查官网", "帮我查询未登记测试大学招生信息", "查官网南京审计大学和北京航空航天大学")) {
            Map<String, Object> clarification = new LinkedHashMap<>(Map.of(
                "action", "ADMISSION_LINKS", "operation", "NONE", "reads", List.of(),
                "clarification", "请只提供一个登记院校全名。"));
            assertDoesNotThrow(() -> AdmissionLinksValidator.validatePlan(clarification, text), text);
        }
        var oneKnownWithoutLinks = new LinkedHashMap<>(Map.of(
            "action", "ADMISSION_LINKS", "operation", "NONE", "reads", List.of(),
            "clarification", "请只提供一个登记院校全名。"));
        assertThrows(IllegalStateException.class,
            () -> AdmissionLinksValidator.validatePlan(oneKnownWithoutLinks, "查官网南京审计大学"));
        var multipleWithLinks = plan();
        assertThrows(IllegalStateException.class,
            () -> AdmissionLinksValidator.validatePlan(multipleWithLinks, "查官网南京审计大学和北京航空航天大学"));
    }

    @Test void completeCatalogRoutesAndResultsAgreeIncludingOverlappingNames() throws Exception {
        JsonNode catalog = json.readTree(new ClassPathResource("admission-sources.json").getInputStream());
        assertEquals(121, catalog.size());
        for (JsonNode school : catalog) {
            String code = school.path("code").asText();
            String name = school.path("name").asText();
            Map<String, Object> value = plan();
            value.put("admissionLinks", query(code));
            for (String spelling : List.of(name, name.replace('（', '(').replace('）', ')'))) {
                assertDoesNotThrow(() -> AdmissionLinksValidator.validatePlan(value,
                    "帮我查询" + spelling + "的招生信息"), spelling);
            }
            Map<String, Object> links = AdmissionLinksValidator.registeredLinks(code);
            assertNotNull(links);
            assertDoesNotThrow(() -> AdmissionLinksValidator.validateResult(
                Map.of("admissionLinks", links), value, "old"), name);
        }
        Map<String, Object> beijing = plan();
        beijing.put("admissionLinks", query("cumtb"));
        for (String text : List.of("查官网中国矿业大学（北京）和中国矿业大学",
            "查官网中国矿业大学和中国矿业大学(北京)")) {
            assertThrows(IllegalStateException.class, () -> AdmissionLinksValidator.validatePlan(beijing, text));
        }
        assertThrows(IllegalStateException.class, () -> AdmissionLinksValidator.validateResult(
            Map.of("admissionLinks", AdmissionLinksValidator.registeredLinks("cumt")), beijing, "old"));
    }

    @Test void exactResultFieldsNamesYearsAndOrderedEntriesAreRequired() throws Exception {
        assertDoesNotThrow(() -> AdmissionLinksValidator.validateResult(output(), plan(), "old"));
        for (String mutation : List.of("code", "name", "year", "entry", "extra", "legacy", "size")) {
            Map<String, Object> value = json.readValue(json.writeValueAsString(output()), LinkedHashMap.class);
            var result = (Map<String, Object>) value.get("admissionLinks");
            switch (mutation) {
                case "code" -> result.put("schoolCode", "buaa");
                case "name" -> result.put("schoolName", "其他大学");
                case "year" -> result.put("registeredYear", 2026);
                case "entry" -> result.put("entryUrls", List.of("https://evil.invalid/"));
                case "extra" -> result.put("status", "CONSISTENT");
                case "legacy" -> value.put("admissionCheck", Map.of("status", "DIFFERENCES"));
                default -> {
                    List<String> entries = new ArrayList<>();
                    for (int index = 0; index < 2000; index++) entries.add("https://gs.nau.edu.cn/" + "a".repeat(40));
                    result.put("entryUrls", entries);
                }
            }
            assertThrows(IllegalStateException.class,
                () -> AdmissionLinksValidator.validateResult(value, plan(), "old"), mutation);
        }
    }

    @Test void legacyProjectionUsesOnlyTheRegisteredSchool() {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("query", Map.of("schoolCode", "nau", "year", 2027, "majorCode", "081200"));
        value.put("entryUrls", List.of("https://evil.invalid/old"));
        value.put("status", "DIFFERENCES");
        JsonNode check = json.valueToTree(value);
        Map<String, Object> projected = AdmissionLinksValidator.legacyLinks(check);
        assertNotNull(projected);
        assertEquals("nau", projected.get("schoolCode"));
        assertEquals("南京审计大学", projected.get("schoolName"));
        assertEquals(2027, projected.get("registeredYear"));
        assertEquals(List.of("https://gs.nau.edu.cn/2026/0920/c4397a161925/page.htm", "https://gs.nau.edu.cn/"),
            projected.get("entryUrls"));
        assertNull(AdmissionLinksValidator.legacyLinks(json.valueToTree(Map.of(
            "query", Map.of("schoolCode", "unknown")))));
        String context = AdmissionLinksValidator.legacyContextAnswer(json.valueToTree(Map.of(
            "answer", "OLD_ANSWER", "admissionCheck", value)));
        assertFalse(context.contains("OLD_ANSWER"));
        assertTrue(context.contains("南京审计大学"));
        assertTrue(context.contains("请自行确认招生年份、专业及报考条件"));
    }
}
