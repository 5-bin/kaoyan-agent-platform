package com.kaoyan;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.export.ExportCache;
import com.kaoyan.export.ExportContracts.*;
import com.kaoyan.security.JwtService;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/** Opt-in actual Redis Lua and JWT/H2 integration, never the daily Redis or MySQL. */
@EnabledIfEnvironmentVariable(named = "KAOYAN_EXPORT_REDIS_TEST", matches = "true")
@SpringBootTest(classes = {KaoyanApplication.class, ExportSmokeServer.Fixtures.class}, properties = {
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.url=jdbc:h2:mem:export-smoke-integration;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER",
    "spring.datasource.username=sa", "spring.datasource.password=",
    "spring.sql.init.mode=always", "spring.sql.init.schema-locations=classpath:schema-test.sql,classpath:schema-practice.sql,classpath:schema-learning-test.sql",
    "jwt.secret=test-only-export-secret-at-least-32-characters", "kaoyan.agent.internal-key=test-only-internal-key-12345",
    "kaoyan.agent.base-url=http://127.0.0.1:9", "oss.endpoint=", "oss.access-key-id=",
    "kaoyan.learning.enabled=true", "kaoyan.learning.initial-delay-ms=3600000"
})
@AutoConfigureMockMvc
@org.springframework.test.annotation.DirtiesContext(classMode = org.springframework.test.annotation.DirtiesContext.ClassMode.AFTER_CLASS)
class ExportIntegrationTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate db;
    @Autowired JwtService jwt;
    @Autowired StringRedisTemplate redis;
    @Autowired ExportCache cache;
    @Autowired com.kaoyan.service.PersonalDocumentService documents;
    static Process server;
    @DynamicPropertySource static void isolatedRedis(DynamicPropertyRegistry properties) throws Exception {
        int port;
        try (var socket = new ServerSocket(0)) { port = socket.getLocalPort(); }
        String executable = System.getenv().getOrDefault("REDIS_SERVER", "redis-server");
        server = new ProcessBuilder(executable, "--bind", "127.0.0.1", "--port", Integer.toString(port), "--save", "", "--appendonly", "no")
                .redirectOutput(ProcessBuilder.Redirect.DISCARD).redirectError(ProcessBuilder.Redirect.DISCARD).start();
        boolean ready = false;
        for (int i = 0; i < 100 && server.isAlive(); i++) {
            try (var socket = new Socket("127.0.0.1", port)) { ready = true; break; }
            catch (java.io.IOException e) { Thread.sleep(50); }
        }
        if (!ready) throw new IllegalStateException("独立Redis未启动");
        properties.add("spring.data.redis.host", () -> "127.0.0.1");
        properties.add("spring.data.redis.port", () -> port);
        properties.add("spring.data.redis.password", () -> "");
    }
    @AfterAll static void stop() throws Exception {
        if (server != null) { server.destroy(); if (!server.waitFor(5, TimeUnit.SECONDS)) server.destroyForcibly(); }
    }
    JsonNode api(MockHttpServletRequestBuilder request, String token, Object body, int status) throws Exception {
        if (token != null) request.header("Authorization", "Bearer " + token);
        if (body != null) request.contentType("application/json").content(json.writeValueAsBytes(body));
        var response = mvc.perform(request).andExpect(status().is(status)).andReturn().getResponse();
        return json.readTree(response.getContentAsByteArray()).path("data");
    }
    String login(int number) throws Exception {
        return api(post("/api/auth/login"), null, Map.of("username", "export_student_" + number, "password", "test-only-export-password"), 200).path("accessToken").asText();
    }
    @Test void ownershipVersionsAllFormatsAndClearedSources() throws Exception {
        String token = login(1), other = login(2);
        String note = api(get("/api/personal-documents"), token, null, 200).path("list").get(0).path("id").asText();
        var input = Map.of("source", "NOTE", "documentId", note, "version", 1);
        api(post("/api/exports/preview"), null, input, 401);
        api(post("/api/exports/preview"), other, input, 404);
        api(post("/api/exports/preview"), token, Map.of("source", "LEARNING_REPORT", "userId", 2), 400);
        JsonNode report = api(post("/api/exports/preview"), token, input, 200);
        assertTrue(report.path("markdown").asText().contains("第一版"));
        assertFalse(report.path("markdown").asText().contains("第二版"));
        String id = report.path("id").asText();
        api(get("/api/exports/" + id), other, null, 404);
        Files.createDirectories(Path.of("target/export-samples"));
        for (String format : List.of("docx", "pdf", "md")) {
            var response = mvc.perform(get("/api/exports/" + id + "/file").param("format", format).header("Authorization", "Bearer " + token))
                    .andExpect(status().isOk()).andExpect(header().string("Cache-Control", "no-store")).andReturn().getResponse();
            assertTrue(response.getHeader("Content-Disposition").contains("filename*="));
            assertTrue(response.getContentAsByteArray().length > 100);
        }
        api(get("/api/exports/" + id + "/file").param("format", "exe"), token, null, 400);
        JsonNode learning = api(post("/api/exports/preview"), token, Map.of("source", "LEARNING_REPORT"), 200);
        assertEquals(3, learning.path("charts").size());
        assertTrue(learning.path("markdown").asText().contains("样本不足"));
        assertTrue(java.util.regex.Pattern.compile("学习时长\\s*\\|\\s*未记录").matcher(learning.path("markdown").asText()).find());
        for (String format : List.of("docx", "pdf", "md")) {
            var response = mvc.perform(get("/api/exports/" + learning.path("id").asText() + "/file").param("format", format).header("Authorization", "Bearer " + token))
                    .andExpect(status().isOk()).andReturn().getResponse();
            Files.write(Path.of("target/export-samples/learning." + format), response.getContentAsByteArray());
        }
        String taskId = UUID.randomUUID().toString();
        long owner = Long.parseLong(jwt.parse(token).getSubject());
        db.update("INSERT INTO task SELECT ?,user_id,task_type,status,input_payload,result_payload,release_id,error_message,created_at,updated_at,deleted_at FROM task WHERE id='export-task'", taskId);
        for (String part : List.of("ANSWER", "STUDY_PLAN", "NOTE_PROPOSAL")) {
            JsonNode result = api(post("/api/exports/preview"), token, Map.of("source", "TASK_RESULT", "taskId", taskId, "part", part), 200);
            assertFalse(result.toString().contains("MUST_NOT_EXPORT_INPUT"));
            if (part.equals("NOTE_PROPOSAL")) {
                assertTrue(result.path("markdown").asText().contains("待确认建议"));
                documents.save(owner, null, new com.kaoyan.service.PersonalDocumentService.Save("已确认合成建议", "正文", null), taskId);
                JsonNode saved = api(post("/api/exports/preview"), token, Map.of("source", "TASK_RESULT", "taskId", taskId, "part", part), 200);
                assertTrue(saved.path("markdown").asText().contains("已确认保存为笔记 v1"));
            }
            if (part.equals("ANSWER")) {
                db.update("UPDATE task SET deleted_at=CURRENT_TIMESTAMP WHERE id=?", taskId);
                api(get("/api/exports/" + result.path("id").asText()), token, null, 404);
                db.update("UPDATE task SET deleted_at=NULL WHERE id=?", taskId);
            }
        }
        db.update("UPDATE task SET status='RUNNING' WHERE id=?", taskId);
        api(post("/api/exports/preview"), token, Map.of("source", "TASK_RESULT", "taskId", taskId, "part", "ANSWER"), 409);
        db.update("DELETE FROM task WHERE id=? AND user_id=?", taskId, owner);
        api(post("/api/auth/logout"), token, null, 200);
        api(get("/api/exports/" + learning.path("id").asText()), token, null, 401);
    }
    @Test void actualRedisLuaAtomicallyEvictsAndRejectsExpiredEntries() throws Exception {
        long owner = 999999;
        Source source = new Source("LEARNING_REPORT", null, null, null, null);
        long now = Instant.now().getEpochSecond();
        var pool = Executors.newFixedThreadPool(4);
        try {
            var futures = java.util.stream.IntStream.range(0, 12).mapToObj(i -> pool.submit(() -> {
                String id = UUID.randomUUID().toString();
                cache.save(owner, new Cached(now + 900, source, new Preview(id, "fixture", "v1", "now", "later", "body", List.of())));
                return id;
            })).toList();
            for (var future : futures) future.get(5, TimeUnit.SECONDS);
        } finally { pool.shutdownNow(); }
        JsonNode entries = json.readTree(redis.opsForValue().get("kaoyan:exports:v1:" + owner));
        assertEquals(5, entries.size());
        assertTrue(redis.getExpire("kaoyan:exports:v1:" + owner) <= 900);
        String id = UUID.randomUUID().toString();
        cache.save(owner, new Cached(now - 1, source, new Preview(id, "expired", "v1", "now", "later", "body", List.of())));
        assertThrows(com.kaoyan.common.ApiException.class, () -> cache.get(owner, id));
    }
}
