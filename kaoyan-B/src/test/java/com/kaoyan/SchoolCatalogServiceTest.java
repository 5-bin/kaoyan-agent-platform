package com.kaoyan;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.service.SchoolCatalogService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(properties = {
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.url=jdbc:h2:mem:school-catalog;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER,YEAR",
    "spring.datasource.username=sa", "spring.datasource.password=", "spring.sql.init.mode=always",
    "spring.sql.init.schema-locations=classpath:schema-test.sql,classpath:schema-school-test.sql,classpath:schema-school-metrics-test.sql",
    "jwt.secret=test-only-jwt-key-at-least-32-characters", "kaoyan.agent.internal-key=test-only-internal-key-12345"
})
@Transactional
class SchoolCatalogServiceTest {
    @Autowired SchoolCatalogService catalog;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper json;
    @MockitoBean StringRedisTemplate redis;

    private void seed() {
        jdbc.update("INSERT INTO school(id,name,province,level) VALUES(11,'四川大学','四川','985'),(12,'未登记测试大学','江苏','普通本科')");
        for (int id = 1; id <= 12; id++) jdbc.update("INSERT INTO school_detail(id,school_id,major_name,major_code,year,remark) VALUES(?,11,'计算机科学与技术','081200',2027,'采集待核实')", id);
        jdbc.update("INSERT INTO school_detail(id,school_id,major_name,major_code,year) VALUES(20,11,'计算机技术','085404',2026)");
    }

    @Test void yearsPreferExplicitThenProfileThenNewestAndNeverChangeYear() {
        seed();
        var plan = SchoolCatalogService.plan("查询四川大学招生信息");
        var latest = json.valueToTree(catalog.answer(plan, Map.of(), Map.of()));
        assertEquals(2027, latest.path("schoolCatalog").path("targetYear").asInt());
        assertEquals(12, latest.path("schoolCatalog").path("total").asInt());
        assertEquals(10, latest.path("schoolCatalog").path("details").size());
        assertEquals(1, latest.path("schoolCatalog").path("details").get(0).path("id").asInt());
        assertTrue(latest.has("admissionLinks"));
        assertEquals("采集待核实", latest.path("schoolCatalog").path("details").get(0).path("remark").asText());
        var profile = json.valueToTree(catalog.answer(plan, Map.of("examYear", 2026), Map.of("majorCodes", List.of("081200"))));
        assertEquals(2026, profile.path("schoolCatalog").path("targetYear").asInt());
        assertEquals("085404", profile.path("schoolCatalog").path("details").get(0).path("majorCode").asText());
        var explicit = json.valueToTree(catalog.answer(SchoolCatalogService.plan("查询四川大学2028年招生目录"), Map.of("examYear", 2027), Map.of()));
        assertEquals(2028, explicit.path("schoolCatalog").path("targetYear").asInt());
        assertEquals(0, explicit.path("schoolCatalog").path("total").asInt());
        assertEquals(2, explicit.path("schoolCatalog").path("availableYears").size());
    }

    @Test void majorFilteringEmptyCatalogAndMissingLinksAreExplicit() {
        seed();
        var filtered = json.valueToTree(catalog.answer(SchoolCatalogService.plan("查询四川大学2027年085404招生信息"), Map.of(), Map.of()));
        assertEquals(0, filtered.path("schoolCatalog").path("total").asInt());
        var empty = json.valueToTree(catalog.answer(SchoolCatalogService.plan("查询未登记测试大学招生信息"), Map.of(), Map.of()));
        assertEquals("未登记测试大学", empty.path("schoolCatalog").path("school").path("name").asText());
        assertTrue(empty.path("schoolCatalog").path("details").isEmpty());
        assertFalse(empty.has("admissionLinks"));
        assertTrue(empty.path("notice").asText().contains("未登记"));
        var missing = catalog.answer(SchoolCatalogService.plan("查询不存在测试大学招生信息"), Map.of(), Map.of());
        assertEquals("UNSUPPORTED", missing.get("outcome"));
        var registeredMissing = json.valueToTree(catalog.answer(SchoolCatalogService.plan("查询北京大学招生信息"), Map.of(), Map.of()));
        assertTrue(registeredMissing.path("schoolCatalog").path("school").isNull());
        assertTrue(registeredMissing.path("answer").asText().contains("尚未收录"));
        assertTrue(registeredMissing.has("admissionLinks"));
    }

    @Test void savedSnapshotDoesNotFollowLaterDatabaseUpdates() throws Exception {
        seed();
        String saved = json.writeValueAsString(catalog.answer(SchoolCatalogService.plan("查询四川大学招生信息"), Map.of(), Map.of()));
        jdbc.update("UPDATE school_detail SET remark='后续变更' WHERE school_id=11");
        assertEquals("采集待核实", json.readTree(saved).path("schoolCatalog").path("details").get(0).path("remark").asText());
    }

    @Test void catalogParametersMustMatchExplicitCurrentQuery() {
        var plan = SchoolCatalogService.plan("查询四川大学2027年081200招生信息");
        assertDoesNotThrow(() -> SchoolCatalogService.validatePlan(plan, "查询四川大学2027年081200招生信息"));
        assertThrows(IllegalStateException.class, () -> SchoolCatalogService.validatePlan(plan, "查询北京大学招生信息"));
        var forged = new LinkedHashMap<>(plan);
        forged.put("reads", List.of("wrong"));
        assertThrows(IllegalStateException.class, () -> SchoolCatalogService.validatePlan(forged, "查询四川大学2027年081200招生信息"));
        assertNotNull(SchoolCatalogService.plan("查询北京大学和清华大学招生信息").get("clarification"));
        assertNull(SchoolCatalogService.plan("给我北京大学招生官网链接"));
        assertNull(SchoolCatalogService.plan("不要查询北京大学招生信息"));
    }
}
