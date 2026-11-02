package com.kaoyan.service;

import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/** Independent plan/result boundaries including expected failures, not just successful queries. */
class AdmissionLinksBoundaryAcceptanceTest {
    private Map<String, Object> plan() {
        return new LinkedHashMap<>(Map.of("action", "ADMISSION_LINKS", "operation", "NONE", "reads", List.of(),
                "admissionLinks", Map.of("schoolCode", "nau")));
    }

    @Test void politeAndFactualSingleSchoolQuestionsRemainValid() {
        for (String query : List.of("请你查官网南京审计大学", "南京审计大学的招生信息有什么变化")) {
            assertTrue(AdmissionLinksValidator.requested(query));
            assertDoesNotThrow(() -> AdmissionLinksValidator.validatePlan(plan(), query));
        }
    }

    @Test void unregisteredSchoolClarificationIsNotAProtocolFailure() {
        Map<String, Object> clarification = plan();
        clarification.remove("admissionLinks");
        clarification.put("clarification", "该校未登记，请选择已登记的院校。");
        assertDoesNotThrow(() -> AdmissionLinksValidator.validatePlan(clarification, "给我未登记测试大学招生网址"));
    }

    @Test void disabledOrUnavailableToolCanReturnUnsupportedWithoutInventingLinks() {
        assertDoesNotThrow(() -> AdmissionLinksValidator.validateResult(
                Map.of("outcome", "UNSUPPORTED", "answer", "招生链接工具不可用", "explanationMode", "rules"),
                plan(), "rag-v1-0000000000000000"));
    }

    @Test void clarificationCannotCarryAnUnrequestedLinkResult() {
        Map<String, Object> clarification = plan();
        clarification.remove("admissionLinks");
        clarification.put("clarification", "请选择一个院校。");
        Map<String, Object> result = Map.of("admissionLinks", Map.of("schoolCode", "nau", "schoolName", "南京审计大学",
                "registeredYear", 2027, "entryUrls", List.of(
                        "https://gs.nau.edu.cn/2026/0920/c4397a161925/page.htm", "https://gs.nau.edu.cn/")));
        assertThrows(IllegalStateException.class, () -> AdmissionLinksValidator.validateResult(
                result, clarification, "rag-v1-0000000000000000"));
    }
}
