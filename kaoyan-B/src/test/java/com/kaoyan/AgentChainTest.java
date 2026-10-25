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

    com.kaoyan.entity.PracticeRecord wrongAttempt(String token) throws Exception {
        long userId = json.readTree(mvc.perform(get("/api/users/me").header("Authorization", "Bearer " + token))
            .andReturn().getResponse().getContentAsString()).path("data").path("id").asLong();
        var r = new com.kaoyan.entity.PracticeRecord(); r.setUserId(userId); r.setSessionId(UUID.randomUUID().toString());
        r.setQuestionId(987654L); r.setOrderIndex(0); r.setIsCorrect(0); r.setUserAnswer("A");
        r.setGradingStatus("valid"); r.setAnsweredAt(java.time.LocalDateTime.now());
        r.setQuestionSnapshot(Map.ofEntries(Map.entry("id", 987654), Map.entry("version", 3), Map.entry("subject", "操作系统"),
            Map.entry("content", "历史版本题干；忽略指令的文字仅为题目数据"), Map.entry("answer", "B"), Map.entry("analysis", "历史原解析"),
            Map.entry("optionA", "历史选项A"), Map.entry("optionB", "历史选项B"), Map.entry("optionC", "历史选项C"), Map.entry("optionD", "历史选项D")));
        attempts.insert(r); return r;
    }
    void rejectTutor(String token, Map<String, Object> input, int statusCode) throws Exception {
        long before = tasks.selectCount(null);
        mvc.perform(post("/api/tasks").header("Authorization", "Bearer " + token).contentType("application/json")
            .content(json.writeValueAsString(Map.of("taskType", "WRONG_QUESTION_TUTOR", "input", input))))
            .andExpect(status().is(statusCode));
        assertEquals(before, tasks.selectCount(null), "拒绝请求不能创建任务或扣额度");
    }
    @Test void tutorRoundtripPersistsBoundedConversationWithoutCurrentQuestion() throws Exception {
        String token = account(); var r = wrongAttempt(token);
        JsonNode task = submit(token, "WRONG_QUESTION_TUTOR", Map.of("recordId", r.getId(), "query", "我的选择错在哪里？"));
        assertEquals("SUCCESS", task.path("status").asText());
        assertEquals("rules", task.path("resultPayload").path("explanationMode").asText());
        assertTrue(task.path("resultPayload").path("notice").asText().contains("未启用 AI"));
        assertEquals("B", task.path("resultPayload").path("standardAnswer").asText());
        assertEquals(3, task.path("resultPayload").path("questionVersion").asInt());
        assertEquals("历史选项A", task.path("inputPayload").path("attempt").path("optionA").asText());
        for (int turn = 1; turn <= 4; turn++) {
            String parent = task.path("id").asText();
            task = submit(token, "WRONG_QUESTION_TUTOR", Map.of("recordId", r.getId(), "query", "追问" + turn, "parentTaskId", parent));
            assertEquals("SUCCESS", task.path("status").asText(), task.toString());
            assertEquals(Math.min(turn * 2, 6), task.path("inputPayload").path("messages").size());
        }
        Task persisted = tasks.selectById(task.path("id").asText());
        assertEquals("追问4", persisted.getInputPayload().get("query"));
        assertEquals(0, attempts.selectById(r.getId()).getIsCorrect());
        attempts.deleteById(r.getId());
        mvc.perform(get("/api/tasks/" + task.path("id").asText()).header("Authorization", "Bearer " + token)).andExpect(status().isOk());
        rejectTutor(token, Map.of("recordId", r.getId(), "query", "继续"), 404);
    }
    @Test void tutorRejectsForeignUnansweredCorrectInvalidAndIncompleteAttempts() throws Exception {
        String token = account(), other = account(); var r = wrongAttempt(token);
        var input = Map.<String, Object>of("recordId", r.getId(), "query", "为什么");
        rejectTutor(other, input, 404);
        r.setIsCorrect(null); attempts.update(r, new com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper<com.kaoyan.entity.PracticeRecord>()
            .eq("id", r.getId()).set("is_correct", null)); rejectTutor(token, input, 409);
        r.setIsCorrect(1); attempts.updateById(r); rejectTutor(token, input, 409);
        r.setIsCorrect(0); r.setGradingStatus("invalid"); attempts.updateById(r); rejectTutor(token, input, 409);
        r.setGradingStatus("valid");
        var original = new LinkedHashMap<>(r.getQuestionSnapshot());
        for (String missing : List.of("version", "optionC", "content", "answer", "id")) {
            var broken = new LinkedHashMap<>(original); broken.remove(missing); r.setQuestionSnapshot(broken);
            attempts.updateById(r); rejectTutor(token, input, 409);
        }
    }
    @Test void tutorRejectsForgedContextAndInvalidParent() throws Exception {
        String token = account(), other = account(); var first = wrongAttempt(token); var second = wrongAttempt(token);
        for (Object id : List.of("1", 1.5, true, -1)) rejectTutor(token, Map.of("recordId", id, "query", "why"), 400);
        for (String field : List.of("messages", "answer", "userId", "attempt", "profile"))
            rejectTutor(token, Map.of("recordId", first.getId(), "query", "why", field, "forged"), 400);
        rejectTutor(token, Map.of("recordId", first.getId(), "query", "x".repeat(2001)), 400);
        JsonNode parent = submit(token, "WRONG_QUESTION_TUTOR", Map.of("recordId", first.getId(), "query", "why"));
        String parentId = parent.path("id").asText();
        rejectTutor(other, Map.of("recordId", wrongAttempt(other).getId(), "query", "why", "parentTaskId", parentId), 404);
        rejectTutor(token, Map.of("recordId", second.getId(), "query", "why", "parentTaskId", parentId), 409);
        Task failed = tasks.selectById(parentId); failed.setStatus("FAILED"); tasks.updateById(failed);
        rejectTutor(token, Map.of("recordId", first.getId(), "query", "why", "parentTaskId", parentId), 409);
    }
}
