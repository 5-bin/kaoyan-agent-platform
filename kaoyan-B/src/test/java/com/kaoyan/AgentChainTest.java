package com.kaoyan;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.mapper.TaskMapper;
import com.kaoyan.entity.Task;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import java.net.*;
import java.net.http.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
    "spring.datasource.url=jdbc:h2:mem:chain;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER",
    "spring.datasource.driver-class-name=org.h2.Driver", "spring.datasource.username=sa", "spring.datasource.password=",
    "spring.sql.init.mode=always", "spring.sql.init.schema-locations=classpath:schema-chain.sql",
    "jwt.secret=test-only-jwt-secret-0123456789abcdefghijklmnopqrstuvwxyz",
    "kaoyan.agent.internal-key=test-only-internal-key-123456", "kaoyan.agent.minute-task-limit=100",
    "kaoyan.agent.daily-task-limit=100", "oss.endpoint=", "oss.access-key-id=", "oss.access-key-secret="
})
@AutoConfigureMockMvc
class AgentChainTest {
    @MockitoBean StringRedisTemplate redis;
    static Process python;
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired TaskMapper tasks;
    @Autowired com.kaoyan.mapper.PracticeRecordMapper attempts;
    @Autowired com.kaoyan.config.AgentProperties props;
    @Autowired com.kaoyan.service.impl.TaskServiceImpl taskService;

    @DynamicPropertySource static void startPython(DynamicPropertyRegistry properties) throws Exception {
        int port;
        try (ServerSocket socket = new ServerSocket(0, 0, InetAddress.getLoopbackAddress())) { port = socket.getLocalPort(); }
        Path agent = Path.of("..", "kaoyan-agent").toAbsolutePath().normalize();
        ProcessBuilder builder = new ProcessBuilder(System.getenv().getOrDefault("PYTHON_EXECUTABLE", "python"),
            "-m", "uvicorn", "main:create_app", "--factory", "--host", "127.0.0.1", "--port", String.valueOf(port));
        builder.directory(agent.toFile());
        builder.environment().put("AGENT_INTERNAL_KEY", "test-only-internal-key-123456");
        builder.environment().put("LLM_ENABLED", "false"); builder.environment().put("RAG_BACKEND", "lexical");
        builder.redirectErrorStream(true).redirectOutput(Path.of("target", "agent-chain.log").toFile());
        python = builder.start();
        Runtime.getRuntime().addShutdownHook(new Thread(() -> { if (python != null) python.destroy(); }));
        String url = "http://127.0.0.1:" + port;
        HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(1)).build();
        boolean ready = false;
        for (int i = 0; i < 100 && python.isAlive(); i++) {
            try {
                ready = client.send(HttpRequest.newBuilder(URI.create(url + "/health")).timeout(Duration.ofSeconds(1)).build(),
                    HttpResponse.BodyHandlers.discarding()).statusCode() == 200;
                if (ready) break;
            } catch (Exception ignored) { }
            Thread.sleep(100);
        }
        if (!ready) { python.destroy(); throw new IllegalStateException("Python未启动，查看target/agent-chain.log"); }
        properties.add("kaoyan.agent.base-url", () -> url);
    }

    @AfterAll static void cleanup() throws Exception {
        if (python != null) { python.destroy(); if (!python.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)) python.destroyForcibly(); }
    }

    String account() throws Exception {
        String username = "chain_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
        String body = json.writeValueAsString(Map.of("username", username, "password", "test-password"));
        mvc.perform(post("/api/auth/register").contentType("application/json").content(body)).andExpect(status().isOk());
        JsonNode login = json.readTree(mvc.perform(post("/api/auth/login").contentType("application/json").content(body))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
        return login.path("data").path("accessToken").asText();
    }
    JsonNode submit(String token, String type, Map<String, Object> input) throws Exception {
        return json.readTree(mvc.perform(post("/api/tasks").header("Authorization", "Bearer " + token)
            .contentType("application/json").content(json.writeValueAsString(Map.of("taskType", type, "input", input))))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString()).path("data");
    }

    @Test void realJavaPythonRulesSourcesAndAccountIsolation() throws Exception {
        String first = account(), second = account();
        mvc.perform(put("/api/users/profile").header("Authorization", "Bearer " + first).contentType("application/json")
            .content("{\"examYear\":2027,\"targetMajor\":\"081200\"}")).andExpect(status().isOk());
        JsonNode task = submit(first, "SCHOOL_RECOMMEND", Map.of("query", "比较目标专业", "preferences", Map.of("degreeType", "academic")));
        assertEquals("SUCCESS", task.path("status").asText());
        assertEquals("COMPLETED", task.path("resultPayload").path("outcome").asText());
        assertEquals(3, task.path("resultPayload").path("candidates").size());
        assertTrue(task.path("releaseId").asText().startsWith("rag-v1-"));
        String id = task.path("id").asText();
        mvc.perform(get("/api/tasks/" + id).header("Authorization", "Bearer " + second)).andExpect(status().isNotFound());
        JsonNode persisted = json.readTree(mvc.perform(get("/api/tasks/" + id).header("Authorization", "Bearer " + first))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString()).path("data");
        assertEquals(task.path("resultPayload"), persisted.path("resultPayload"));
        mvc.perform(put("/api/users/profile").header("Authorization", "Bearer " + first).contentType("application/json")
            .content("{\"examYear\":2026,\"targetMajor\":\"081200\"}")).andExpect(status().isOk());
        assertEquals(2027, tasks.selectById(id).getResultPayload().containsKey("profileSnapshot")
            ? ((Map<?, ?>) tasks.selectById(id).getResultPayload().get("profileSnapshot")).get("examYear") : 0);
    }

    @Test void shortKnowledgeQueryHasSourcesAndUnknownTopicDoesNot() throws Exception {
        String token = account();
        JsonNode known = submit(token, "KNOWLEDGE_QA", Map.of("query", "进程与线程"));
        assertEquals("SUCCESS", known.path("status").asText());
        assertTrue(known.path("resultPayload").path("references").size() > 0);
        JsonNode unknown = submit(token, "KNOWLEDGE_QA", Map.of("query", "海水观赏鱼繁育"));
        assertEquals("UNSUPPORTED", unknown.path("resultPayload").path("outcome").asText());
    }

    @Test void invalidAndForgedRequestsAreRejected() throws Exception {
        String token = account();
        for (String body : List.of("{\"taskType\":\"TYPO\",\"input\":{}}",
            "{\"taskType\":\"KNOWLEDGE_QA\",\"ownerId\":9,\"input\":{\"query\":\"x\"}}",
            "{\"taskType\":\"KNOWLEDGE_QA\",\"input\":{\"query\":\"x\",\"profile\":{}}}"))
            mvc.perform(post("/api/tasks").header("Authorization", "Bearer " + token).contentType("application/json").content(body))
                .andExpect(status().isBadRequest());
    }

    @Test void limitRejectsBeforeAnotherRemoteCall() throws Exception {
        String token = account();
        int old = props.getDailyTaskLimit();
        props.setDailyTaskLimit(1);
        try {
            submit(token, "KNOWLEDGE_QA", Map.of("query", "TCP可靠传输"));
            mvc.perform(post("/api/tasks").header("Authorization", "Bearer " + token).contentType("application/json")
                .content("{\"taskType\":\"KNOWLEDGE_QA\",\"input\":{\"query\":\"TCP可靠传输\"}}"))
                .andExpect(status().isTooManyRequests());
        } finally { props.setDailyTaskLimit(old); }
    }

    @Test void restartMarksInterruptedTaskWithoutFakingCompletion() {
        Task task = new Task(); task.setId(UUID.randomUUID().toString()); task.setUserId(999L);
        task.setTaskType("KNOWLEDGE_QA"); task.setStatus("RUNNING");
        tasks.insert(task);
        taskService.run(null);
        assertEquals("FAILED", tasks.selectById(task.getId()).getStatus());
        assertNull(tasks.selectById(task.getId()).getResultPayload());
    }

    @Test void realSummaryUsesOnlyOwnedStoredSnapshot() throws Exception {
        String owner = account(), other = account();
        JsonNode me = json.readTree(mvc.perform(get("/api/users/me").header("Authorization", "Bearer " + owner))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString()).path("data");
        assertFalse(me.has("passwordHash"));
        com.kaoyan.entity.PracticeRecord record = new com.kaoyan.entity.PracticeRecord();
        record.setUserId(me.path("id").asLong()); record.setSessionId("snapshot-session"); record.setQuestionId(123456L);
        record.setOrderIndex(0); record.setIsCorrect(0); record.setGradingStatus("valid");
        record.setQuestionSnapshot(Map.of("id", 123456, "version", 2, "subject", "操作系统",
            "knowledgePoint", "线程", "content", "已判分的历史版本题干", "answer", "A"));
        var expandedSnapshot = new LinkedHashMap<String, Object>(record.getQuestionSnapshot());
        expandedSnapshot.put("optionA", "历史选项A"); expandedSnapshot.put("optionB", "历史选项B");
        expandedSnapshot.put("optionC", null); expandedSnapshot.put("optionD", null);
        expandedSnapshot.put("difficulty", "EASY");
        record.setQuestionSnapshot(expandedSnapshot);
        attempts.insert(record);
        var correctRecord = new com.kaoyan.entity.PracticeRecord();
        correctRecord.setUserId(me.path("id").asLong()); correctRecord.setSessionId("snapshot-session");
        correctRecord.setQuestionId(123457L); correctRecord.setOrderIndex(1); correctRecord.setIsCorrect(1);
        correctRecord.setGradingStatus("valid");
        correctRecord.setQuestionSnapshot(Map.of("id", 123457, "version", 1, "subject", "操作系统",
            "content", "另一道已判分历史题", "answer", "B"));
        attempts.insert(correctRecord);
        JsonNode task = submit(owner, "PRACTICE_SUMMARY", Map.of("sessionId", "snapshot-session"));
        assertEquals("SUCCESS", task.path("status").asText());
        assertEquals(1, task.path("resultPayload").path("correct").asInt());
        assertEquals(2, task.path("resultPayload").path("total").asInt());
        assertEquals(50.0, task.path("resultPayload").path("accuracy").asDouble());
        assertEquals(2, task.path("inputPayload").path("questions").get(0).path("version").asInt());
        mvc.perform(post("/api/tasks").header("Authorization", "Bearer " + other).contentType("application/json")
            .content("{\"taskType\":\"PRACTICE_SUMMARY\",\"input\":{\"sessionId\":\"snapshot-session\"}}"))
            .andExpect(status().isNotFound());
    }
}
