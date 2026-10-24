package com.kaoyan;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;
import java.util.UUID;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.url=jdbc:h2:mem:school-options;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER,YEAR",
    "spring.datasource.username=sa", "spring.datasource.password=",
    "spring.sql.init.mode=always",
    "spring.sql.init.schema-locations=classpath:schema-test.sql,classpath:schema-school-test.sql",
    "jwt.secret=test-only-jwt-key-at-least-32-characters",
    "kaoyan.agent.internal-key=test-only-internal-key-12345"
})
@AutoConfigureMockMvc
@Transactional
class SchoolOptionsIntegrationTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @Autowired JdbcTemplate jdbc;
    @Autowired org.mybatis.spring.SqlSessionTemplate sqlSession;
    @MockitoBean StringRedisTemplate redis;

    private String login() throws Exception {
        String body = mapper.writeValueAsString(Map.of(
            "username", "s" + UUID.randomUUID().toString().substring(0, 8), "password", "test-password"));
        mvc.perform(post("/api/auth/register").contentType("application/json").content(body))
            .andExpect(status().isOk());
        return mapper.readTree(mvc.perform(post("/api/auth/login").contentType("application/json").content(body))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString())
            .path("data").path("accessToken").asText();
    }

    private void seed() {
        jdbc.update("INSERT INTO school(id,name,province,level) VALUES " +
            "(1,'测试甲校','北京','985'),(2,'测试乙校','江苏','211'),(3,'测试丙校','北京','211')," +
            "(4,'空省份校','   ',NULL),(5,'未登记省份校',NULL,NULL),(6,'空字符串校','',NULL)");
        jdbc.update("INSERT INTO school_detail(school_id,major_name,year) VALUES " +
            "(1,'计算机科学与技术',2027),(1,'计算机科学与技术',2026),(2,'软件工程',2027)," +
            "(3,'计算机技术',2027),(3,'软件工程',2026),(1,NULL,2027),(1,'   ',2027),(1,'',2027)," +
            "(999,'孤立专业',2027)");
    }

    @Test void optionsRequireAuthentication() throws Exception {
        mvc.perform(get("/api/schools/options")).andExpect(status().isUnauthorized());
    }

    @Test void emptyCatalogReturnsEmptyArrays() throws Exception {
        mvc.perform(get("/api/schools/options").header("Authorization", "Bearer " + login()))
            .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(0))
            .andExpect(jsonPath("$.data.provinces").isEmpty())
            .andExpect(jsonPath("$.data.majorNames").isEmpty());
    }

    @Test void optionsAreSortedDistinctNonBlankAndExcludeOrphans() throws Exception {
        seed();
        String token = login();
        mvc.perform(get("/api/schools/options").header("Authorization", "Bearer " + token))
            .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(0))
            .andExpect(jsonPath("$.data.provinces", contains("北京", "江苏")))
            .andExpect(jsonPath("$.data.majorNames", contains("计算机技术", "计算机科学与技术", "软件工程")));
        // The options endpoint is a live read, not a frontend or server startup snapshot.
        jdbc.update("INSERT INTO school(id,name,province) VALUES(7,'新增校','河北')");
        jdbc.update("INSERT INTO school_detail(school_id,major_name) VALUES(7,'新增专业')");
        // JDBC fixtures bypass MyBatis invalidation inside this rollback-only test transaction.
        sqlSession.clearCache();
        mvc.perform(get("/api/schools/options").header("Authorization", "Bearer " + token))
            .andExpect(jsonPath("$.data.provinces", contains("北京", "江苏", "河北")))
            .andExpect(jsonPath("$.data.majorNames", contains("新增专业", "计算机技术", "计算机科学与技术", "软件工程")));
    }

    @Test void existingGetAndPostFiltersAndDetailRemainCompatible() throws Exception {
        seed();
        String token = login();
        mvc.perform(get("/api/schools").header("Authorization", "Bearer " + token)
            .param("province", "北京").param("level", "985").param("majorName", "计算机科学与技术"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.data", hasSize(1)))
            .andExpect(jsonPath("$.data[0].name").value("测试甲校"));
        mvc.perform(post("/api/schools/search").header("Authorization", "Bearer " + token)
            .contentType("application/json").content("{\"province\":\"江苏\",\"majorName\":\"软件\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.data", hasSize(1)))
            .andExpect(jsonPath("$.data[0].name").value("测试乙校"));
        mvc.perform(get("/api/schools").header("Authorization", "Bearer " + token)
            .param("province", "").param("level", "").param("majorName", ""))
            .andExpect(status().isOk()).andExpect(jsonPath("$.data", hasSize(6)));
        mvc.perform(get("/api/schools/2").header("Authorization", "Bearer " + token))
            .andExpect(status().isOk()).andExpect(jsonPath("$.data.school.name").value("测试乙校"))
            .andExpect(jsonPath("$.data.details[0].majorName").value("软件工程"));
    }
}
