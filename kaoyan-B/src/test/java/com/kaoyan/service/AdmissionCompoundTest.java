package com.kaoyan.service;

import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

/** Mirrors kaoyan-agent/tests/test_review_p2.py COMPOUND / SINGLE verbatim. */
class AdmissionCompoundTest {
    static final List<String> COMPOUND = List.of(
        "查询北京大学招生信息并解释TCP可靠传输",
        "给我北京大学招生官网链接，并安排3天复习计划",
        "查询北京大学招生信息，再推荐几所类似院校",
        "查询北京大学招生目录，顺便做几道TCP题");
    static final List<String> SINGLE = List.of(
        "查询北京大学招生信息",
        "给我北京大学招生官网链接",
        "查询北京大学统计学专业招生信息",
        "查询北京大学计算机组成原理方向招生目录",
        "推荐南京审计大学并给我招生网址");

    @Test void detectsTheSameCompoundTurnsAsPython() {
        for (String query : COMPOUND) assertTrue(AdmissionLinksValidator.compound(query), query);
        for (String query : SINGLE) assertFalse(AdmissionLinksValidator.compound(query), query);
    }

    @Test void compoundLookupClarifiesWithoutParameters() {
        for (String query : List.of(COMPOUND.get(0), COMPOUND.get(2), COMPOUND.get(3))) {
            var plan = SchoolCatalogService.plan(query);
            assertEquals(AdmissionLinksValidator.SPLIT, plan.get("clarification"), query);
            assertNull(plan.get("schoolLookup"), query);
            assertDoesNotThrow(() -> SchoolCatalogService.validatePlan(plan, query));
        }
        // Link requests are planned by Python; a CHAT clarification passes the link validator.
        assertNull(SchoolCatalogService.plan(COMPOUND.get(1)));
        var chat = new java.util.HashMap<String, Object>(java.util.Map.of("action", "CHAT", "clarification", AdmissionLinksValidator.SPLIT));
        assertDoesNotThrow(() -> AdmissionLinksValidator.validatePlan(chat, COMPOUND.get(1)));
        var single = SchoolCatalogService.plan(SINGLE.get(0));
        assertNull(single.get("clarification"));
        assertNotNull(single.get("schoolLookup"));
    }
}
