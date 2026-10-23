package com.kaoyan;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.entity.Question;
import com.kaoyan.mapper.QuestionMapper;
import com.kaoyan.security.JwtService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.url=jdbc:h2:mem:question-entry;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER",
    "spring.datasource.username=sa", "spring.datasource.password=",
    "spring.sql.init.mode=always", "spring.sql.init.schema-locations=classpath:schema-test.sql,classpath:schema-practice.sql",
    "jwt.secret=test-only-question-entry-secret-0123456789abcdefghijk",
    "kaoyan.agent.internal-key=test-only-entry-internal-123456", "oss.endpoint=", "oss.access-key-id="
})
@AutoConfigureMockMvc
class QuestionEntryReviewTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate jdbc;
    @Autowired JwtService jwt;
    @Autowired QuestionMapper questions;
    @MockitoBean StringRedisTemplate redis;

    JsonNode call(MockHttpServletRequestBuilder request, String token, Object body, int expected) throws Exception {
        if (token != null) request.header("Authorization", "Bearer " + token);
        if (body != null) request.contentType("application/json").content(json.writeValueAsString(body));
        return json.readTree(mvc.perform(request).andExpect(status().is(expected)).andReturn().getResponse().getContentAsString()).path("data");
    }
    String account(boolean admin) throws Exception {
        String username = "qe_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
        var credentials = Map.of("username", username, "password", "entry-test-password");
        call(post("/api/auth/register"), null, credentials, 200);
        if (admin) jdbc.update("UPDATE `user` SET role='ADMIN' WHERE username=?", username);
        return call(post("/api/auth/login"), null, credentials, 200).path("accessToken").asText();
    }
    Map<String, Object> entry() {
        Map<String, Object> b = new LinkedHashMap<>();
        b.put("subject", "数据结构"); b.put("knowledgePoint", "entry_" + UUID.randomUUID().toString().substring(0, 12));
        b.put("difficulty", "EASY"); b.put("content", "自编验证题：栈的出栈次序遵循什么规则？");
        b.put("optionA", "后进先出"); b.put("optionB", "先进先出"); b.put("optionC", "随机"); b.put("optionD", "按大小排序");
        b.put("answer", "a"); b.put("analysis", "栈只在栈顶执行入栈和出栈，所以后入栈的元素先出栈。");
        b.put("sourceType", "ORIGINAL"); b.put("sourceName", "隔离测试自编题"); b.put("sourceLocator", "测试用例entry记录");
        b.put("permissionNote", "本题为工程测试自编，不声明真题来源。");
        return b;
    }
    long create(String admin, Map<String, Object> body) throws Exception {
        return call(post("/api/questions/admin"), admin, body, 200).path("id").asLong();
    }
    JsonNode detail(String admin, long id) throws Exception { return call(get("/api/questions/admin/" + id), admin, null, 200); }
    void review(String admin, long id, String state, String comment, int version, int expected) throws Exception {
        call(post("/api/questions/admin/" + id + "/review"), admin, Map.of("status", state, "comment", comment, "version", version), expected);
    }
    JsonNode edit(String admin, long id, Map<String, Object> body, int version, int expected) throws Exception {
        var request = new LinkedHashMap<>(body); request.put("version", version);
        return call(put("/api/questions/admin/" + id), admin, request, expected);
    }
    JsonNode active(String admin, long id, int value, int version, int expected) throws Exception {
        return call(put("/api/questions/admin/" + id + "/active"), admin,
            Map.of("active", value, "version", version), expected);
    }
    JsonNode candidates(String student, Map<String, Object> body) throws Exception {
        return call(get("/api/questions/practice").param("knowledgePoint", body.get("knowledgePoint").toString()), student, null, 200);
    }

    @Test void administratorCanEnterReviewAndPracticeWithoutLeakingAnswers() throws Exception {
        String admin = account(true), student = account(false);
        var body = entry(); long id = create(admin, body);
        var pending = detail(admin, id);
        assertEquals("PENDING_REVIEW", pending.path("reviewStatus").asText());
        assertEquals("A", pending.path("answer").asText()); assertEquals(1, pending.path("version").asInt());
        assertEquals("ORIGINAL", questions.selectById(id).getSourceType());
        assertEquals(0, candidates(student, body).size());
        call(get("/api/questions/" + id), student, null, 404);
        var page = call(get("/api/questions/admin/pending?pageNum=1&pageSize=100"), admin, null, 200);
        assertTrue(page.path("list").findValues("id").stream().anyMatch(n -> n.asLong() == id));
        review(admin, id, "APPROVED", "已核对题目和自编说明", 1, 200);
        var approved = detail(admin, id);
        assertEquals(Long.parseLong(jwt.parse(admin).getSubject()), approved.path("reviewerUserId").asLong());
        assertFalse(approved.path("reviewedAt").isNull());
        var visible = candidates(student, body); assertEquals(1, visible.size());
        assertFalse(visible.get(0).has("answer")); assertFalse(visible.get(0).has("permissionNote"));
        var publicDetail = call(get("/api/questions/" + id), student, null, 200);
        assertFalse(publicDetail.has("analysis")); assertFalse(publicDetail.has("sourceLocator"));
        String session = call(post("/api/practice/sessions"), student, Map.of("subject", "数据结构", "count", 50), 200).path("sessionId").asText();
        var result = call(post("/api/practice/sessions/" + session + "/answer"), student, Map.of("questionId", id, "answer", "A"), 200);
        assertEquals(1, result.path("isCorrect").asInt());
        edit(admin, id, body, 2, 409);
        assertEquals("APPROVED", questions.selectById(id).getReviewStatus());
        var snapshot = jdbc.queryForObject("SELECT question_snapshot FROM practice_record WHERE session_id=? AND question_id=?", String.class, session, id);
        assertEquals(body.get("content"), json.readTree(snapshot).path("content").asText());
    }

    @Test void invalidEntriesAndForgedPublicationFieldsNeverWrite() throws Exception {
        String admin = account(true); long before = questions.selectCount(null);
        for (String field : List.of("content", "knowledgePoint", "optionA", "optionB", "optionC", "optionD", "analysis", "sourceName", "sourceLocator", "permissionNote")) {
            var body = entry(); body.put(field, "  "); call(post("/api/questions/admin"), admin, body, 400);
        }
        for (String field : List.of("id", "active", "version", "reviewStatus", "reviewerUserId", "reviewedAt", "stableOrder", "questionType")) {
            var body = entry(); body.put(field, field.equals("reviewStatus") ? "APPROVED" : 1);
            call(post("/api/questions/admin"), admin, body, 400);
        }
        for (var pair : Map.of("answer", "AB", "sourceType", "SCRAPED", "subject", "英语", "difficulty", "UNKNOWN").entrySet()) {
            var body = entry(); body.put(pair.getKey(), pair.getValue()); call(post("/api/questions/admin"), admin, body, 400);
        }
        var body = entry(); body.put("sourceYear", 1800); call(post("/api/questions/admin"), admin, body, 400);
        body = entry(); body.put("sourceName", "x".repeat(256)); call(post("/api/questions/admin"), admin, body, 400);
        assertEquals(before, questions.selectCount(null));
    }

    @Test void realExamRequiresYearAndOriginalNumberAndAllSourcesPersist() throws Exception {
        String admin = account(true); var body = entry(); body.put("sourceType", "REAL_EXAM");
        call(post("/api/questions/admin"), admin, body, 400);
        body.put("sourceYear", 2024); call(post("/api/questions/admin"), admin, body, 400);
        body.put("sourceQuestionNo", "第1题"); long id = create(admin, body);
        var q = detail(admin, id); assertEquals(2024, q.path("sourceYear").asInt());
        assertEquals("第1题", q.path("sourceQuestionNo").asText());
        for (String key : List.of("sourceType", "sourceName", "sourceLocator", "permissionNote")) assertEquals(body.get(key), q.path(key).asText());
        var mock = entry(); mock.put("sourceType", "MOCK"); assertTrue(create(admin, mock) > 0);
    }

    @Test void studentsCannotUseAnyManagementRouteOrForgeReviewerIdentity() throws Exception {
        String admin = account(true), student = account(false); long id = create(admin, entry());
        call(post("/api/questions/admin"), student, entry(), 403);
        call(get("/api/questions/admin/pending"), student, null, 403);
        call(get("/api/questions/admin/" + id), student, null, 403);
        call(put("/api/questions/admin/" + id), student, entry(), 403);
        call(delete("/api/questions/admin/" + id), student, null, 403);
        review(student, id, "APPROVED", "", 1, 403);
        call(get("/api/questions/admin/" + id), null, null, 401);
        var forged = new HashMap<String, Object>(Map.of("status", "APPROVED", "version", 1, "reviewerUserId", 999));
        call(post("/api/questions/admin/" + id + "/review"), admin, forged, 400);
        assertNull(questions.selectById(id).getReviewerUserId());
    }

    @Test void rejectionResubmissionAndStaleReviewPreserveServerState() throws Exception {
        String admin = account(true), student = account(false); var body = entry();
        body.put("sourceYear", 2024); body.put("sourceQuestionNo", "old-no"); long id = create(admin, body);
        review(admin, id, "PUBLISHED", "", 1, 400); review(admin, id, "REJECTED", "  ", 1, 400);
        call(post("/api/questions/admin/" + id + "/review"), admin, Map.of("status", "APPROVED"), 400);
        review(admin, id, "REJECTED", "解析需补充", 1, 200);
        assertEquals("解析需补充", detail(admin, id).path("reviewComment").asText());
        assertEquals(0, candidates(student, body).size()); review(admin, id, "APPROVED", "", 1, 409);
        body.remove("sourceYear"); body.remove("sourceQuestionNo"); body.put("analysis", "修改后的完整解析");
        var updated = edit(admin, id, body, 2, 200);
        assertEquals(3, updated.path("version").asInt()); assertEquals("PENDING_REVIEW", updated.path("reviewStatus").asText());
        for (String key : List.of("reviewComment", "reviewerUserId", "reviewedAt", "sourceYear", "sourceQuestionNo")) assertTrue(updated.path(key).isNull(), key);
        review(admin, id, "APPROVED", "旧页面", 1, 409); review(admin, id, "APPROVED", "新页面", 3, 200);
        review(admin, id, "REJECTED", "重复审核", 2, 409);
        assertEquals("APPROVED", questions.selectById(id).getReviewStatus());
    }

    @Test void legacyMissingSourceMustBeCompletedBeforeApprovalAndDisabledQuestionsRemainDisabled() throws Exception {
        String admin = account(true); var body = entry(); long id = create(admin, body);
        jdbc.update("UPDATE question SET source_type=NULL,source_name=NULL,permission_note=NULL,active=0 WHERE id=?", id);
        assertTrue(detail(admin, id).path("sourceType").isNull());
        review(admin, id, "APPROVED", "", 1, 400);
        edit(admin, id, body, 1, 200);
        review(admin, id, "APPROVED", "已补来源", 2, 200);
        assertEquals(0, questions.selectById(id).getActive());
        call(get("/api/questions/" + id), account(false), null, 404);
        call(get("/api/questions/admin/9999999"), admin, null, 404);
    }

    @Test void concurrentReviewersHaveOnlyOneDecision() throws Exception {
        String first = account(true), second = account(true); long id = create(first, entry());
        var pool = Executors.newFixedThreadPool(2); var gate = new CountDownLatch(1);
        try {
            Callable<Integer> approve = () -> { gate.await(10, TimeUnit.SECONDS); return reviewStatus(first, id, "APPROVED"); };
            Callable<Integer> reject = () -> { gate.await(10, TimeUnit.SECONDS); return reviewStatus(second, id, "REJECTED"); };
            var a = pool.submit(approve); var b = pool.submit(reject); gate.countDown();
            var states = new ArrayList<>(List.of(a.get(20, TimeUnit.SECONDS), b.get(20, TimeUnit.SECONDS))); Collections.sort(states);
            assertEquals(List.of(200, 409), states);
        } finally { pool.shutdownNow(); }
        var q = questions.selectById(id);
        String winner = "APPROVED".equals(q.getReviewStatus()) ? first : second;
        assertEquals(Long.parseLong(jwt.parse(winner).getSubject()), q.getReviewerUserId());
    }
    @Test void staleEditorsCannotOverwriteSavedContentOrClearLaterRejection() throws Exception {
        String first = account(true), second = account(true); var body = entry(); long id = create(first, body);
        var correction = new LinkedHashMap<>(body); correction.put("answer", "B");
        edit(second, id, correction, 1, 200);
        var stale = new LinkedHashMap<>(body); stale.put("analysis", "旧页面的解析");
        edit(first, id, stale, 1, 409);
        assertEquals("B", detail(first, id).path("answer").asText());
        assertEquals(body.get("analysis"), detail(first, id).path("analysis").asText());
        review(second, id, "REJECTED", "需核对答案依据", 2, 200);
        edit(first, id, stale, 2, 409);
        var rejected = detail(first, id);
        assertEquals(3, rejected.path("version").asInt());
        assertEquals("REJECTED", rejected.path("reviewStatus").asText());
        assertEquals("需核对答案依据", rejected.path("reviewComment").asText());
    }

    @Test void missingForgedAndOutdatedMutationVersionsNeverWrite() throws Exception {
        String admin = account(true); var body = entry(); long id = create(admin, body);
        call(put("/api/questions/admin/" + id), admin, body, 400);
        for (Object version : Arrays.asList(null, 0, -1, 1.5, "1", "invalid")) {
            var request = new LinkedHashMap<>(body); request.put("version", version);
            call(put("/api/questions/admin/" + id), admin, request, 400);
        }
        call(post("/api/questions/admin/" + id + "/review"), admin,
            Map.of("status", "APPROVED", "version", 1.5), 400);
        var forged = new LinkedHashMap<>(body); forged.put("version", 1); forged.put("active", 0);
        call(put("/api/questions/admin/" + id), admin, forged, 400);
        edit(admin, id, body, 999, 409);
        assertEquals(1, detail(admin, id).path("version").asInt());
    }

    @Test void concurrentEditorsAndEditorAgainstReviewerHaveOnlyOneWinner() throws Exception {
        String first = account(true), second = account(true); var body = entry(); long id = create(first, body);
        var a = new LinkedHashMap<>(body); a.put("answer", "B"); a.put("version", 1);
        var b = new LinkedHashMap<>(body); b.put("answer", "C"); b.put("version", 1);
        race(first, put("/api/questions/admin/" + id), a, second, put("/api/questions/admin/" + id), b);
        assertEquals(2, detail(first, id).path("version").asInt());
        assertTrue(Set.of("B", "C").contains(detail(first, id).path("answer").asText()));
        long next = create(first, body); a.put("version", 1);
        race(first, put("/api/questions/admin/" + next), a, second,
            post("/api/questions/admin/" + next + "/review"), Map.of("status", "REJECTED", "comment", "需补充", "version", 1));
        assertEquals(2, detail(first, next).path("version").asInt());
    }

    @Test void activationChecksPermissionsInputAndApprovedState() throws Exception {
        String admin = account(true), student = account(false); long id = create(admin, entry());
        active(student, id, 0, 1, 403);
        call(put("/api/questions/admin/" + id + "/active"), null, Map.of("active", 0, "version", 1), 401);
        active(admin, id, 0, 1, 409);
        review(admin, id, "REJECTED", "待核对", 1, 200); active(admin, id, 1, 2, 409);
        long approved = create(admin, entry()); review(admin, approved, "APPROVED", "已核对", 1, 200);
        String path = "/api/questions/admin/" + approved + "/active";
        for (Object invalid : Arrays.asList(null, -1, 2, 0.5, "0", "invalid")) {
            var request = new LinkedHashMap<String,Object>(); request.put("active", invalid); request.put("version", 2);
            call(put(path), admin, request, 400);
        }
        call(put(path), admin, Map.of("active", 0), 400);
        call(put(path), admin, Map.of("active", 0, "version", 0), 400);
        call(put(path), admin, Map.of("active", 0, "version", 2, "reviewStatus", "APPROVED"), 400);
        active(admin, approved, 1, 2, 409); active(admin, approved, 0, 1, 409);
        active(admin, 99999999, 0, 2, 404);
        assertEquals(2, detail(admin, approved).path("version").asInt());
    }

    @Test void disablingAndRestoringPreservesAuditSourcesSnapshotsAndStatistics() throws Exception {
        String admin = account(true), student = account(false); var body = entry(); long id = create(admin, body);
        review(admin, id, "APPROVED", "保留审核依据", 1, 200);
        String first = call(post("/api/practice/sessions"), student, Map.of("subject", "数据结构", "count", 50), 200).path("sessionId").asText();
        call(post("/api/practice/sessions/" + first + "/answer"), student, Map.of("questionId", id, "answer", "B"), 200);
        String second = call(post("/api/practice/sessions"), student, Map.of("subject", "数据结构", "count", 50), 200).path("sessionId").asText();
        var records = jdbc.queryForList("SELECT * FROM practice_record WHERE question_id=? ORDER BY id", id);
        var stats = jdbc.queryForList("SELECT * FROM study_stat");
        var marks = jdbc.queryForList("SELECT * FROM user_question_mark");
        var before = detail(admin, id);
        var stopped = active(admin, id, 0, 2, 200);
        assertEquals(0, stopped.path("active").asInt()); assertEquals(3, stopped.path("version").asInt());
        assertEquals(0, candidates(student, body).size()); call(get("/api/questions/" + id), student, null, 404);
        call(post("/api/practice/sessions/" + second + "/answer"), student, Map.of("questionId", id, "answer", "A"), 409);
        active(admin, id, 0, 3, 409); active(admin, id, 1, 2, 409);
        var restored = active(admin, id, 1, 3, 200);
        assertEquals(4, restored.path("version").asInt()); assertEquals(1, candidates(student, body).size());
        for (String key : List.of("content", "answer", "analysis", "sourceType", "sourceName", "sourceLocator",
                "sourceYear", "sourceQuestionNo", "permissionNote", "reviewStatus", "reviewerUserId", "reviewedAt", "reviewComment"))
            assertEquals(before.path(key), restored.path(key), key);
        assertEquals(records, jdbc.queryForList("SELECT * FROM practice_record WHERE question_id=? ORDER BY id", id));
        assertEquals(stats, jdbc.queryForList("SELECT * FROM study_stat"));
        assertEquals(marks, jdbc.queryForList("SELECT * FROM user_question_mark"));
        call(post("/api/practice/sessions/" + second + "/answer"), student, Map.of("questionId", id, "answer", "A"), 200);
        assertEquals(records.get(0).get("QUESTION_SNAPSHOT"), jdbc.queryForObject(
            "SELECT question_snapshot FROM practice_record WHERE session_id=? AND question_id=?", String.class, first, id));
    }

    @Test void onlyEntirelyUndocumentedLegacySourcesCanBypassSourceValidationOnRestore() throws Exception {
        String admin = account(true); var body = entry();
        long legacy = create(admin, body); review(admin, legacy, "APPROVED", "历史审核", 1, 200);
        jdbc.update("UPDATE question SET source_type=NULL,source_name=NULL,source_locator=NULL,source_year=NULL,source_question_no=NULL,permission_note=NULL WHERE id=?", legacy);
        active(admin, legacy, 0, 2, 200); var restored = active(admin, legacy, 1, 3, 200);
        for (String field : List.of("sourceType", "sourceName", "sourceLocator", "sourceYear", "sourceQuestionNo", "permissionNote"))
            assertTrue(restored.path(field).isNull());
        active(admin, legacy, 0, 4, 200);
        jdbc.update("UPDATE question SET answer='Z' WHERE id=?", legacy); active(admin, legacy, 1, 5, 400);
        jdbc.update("UPDATE question SET answer='A',question_type='MULTIPLE_CHOICE' WHERE id=?", legacy); active(admin, legacy, 1, 5, 400);
        long partial = create(admin, body); review(admin, partial, "APPROVED", "已核对", 1, 200);
        active(admin, partial, 0, 2, 200);
        jdbc.update("UPDATE question SET permission_note=NULL WHERE id=?", partial); active(admin, partial, 1, 3, 400);
        jdbc.update("UPDATE question SET source_type='',source_name=NULL,source_locator=NULL,permission_note=NULL WHERE id=?", partial);
        active(admin, partial, 1, 3, 400);
        assertEquals(0, detail(admin, partial).path("active").asInt());
        assertEquals(3, detail(admin, partial).path("version").asInt());
    }

    @Test void concurrentActivationRequestsOnlyChangeStateOnce() throws Exception {
        String first = account(true), second = account(true); long id = create(first, entry());
        review(first, id, "APPROVED", "已核对", 1, 200);
        race(first, put("/api/questions/admin/" + id + "/active"), Map.of("active", 0, "version", 2),
            second, put("/api/questions/admin/" + id + "/active"), Map.of("active", 0, "version", 2));
        assertEquals(3, detail(first, id).path("version").asInt());
        assertEquals(0, detail(first, id).path("active").asInt());
    }

    void race(String first, MockHttpServletRequestBuilder firstRequest, Object firstBody,
              String second, MockHttpServletRequestBuilder secondRequest, Object secondBody) throws Exception {
        var pool = Executors.newFixedThreadPool(2); var gate = new CountDownLatch(1);
        try {
            Callable<Integer> a = () -> { gate.await(10, TimeUnit.SECONDS); return mutationStatus(first, firstRequest, firstBody); };
            Callable<Integer> b = () -> { gate.await(10, TimeUnit.SECONDS); return mutationStatus(second, secondRequest, secondBody); };
            var x = pool.submit(a); var y = pool.submit(b); gate.countDown();
            var states = new ArrayList<>(List.of(x.get(20, TimeUnit.SECONDS), y.get(20, TimeUnit.SECONDS))); Collections.sort(states);
            assertEquals(List.of(200, 409), states);
        } finally { pool.shutdownNow(); }
    }
    int mutationStatus(String token, MockHttpServletRequestBuilder request, Object body) throws Exception {
        return mvc.perform(request.header("Authorization", "Bearer " + token).contentType("application/json")
            .content(json.writeValueAsString(body))).andReturn().getResponse().getStatus();
    }

    int reviewStatus(String token, long id, String decision) throws Exception {
        return mvc.perform(post("/api/questions/admin/" + id + "/review").header("Authorization", "Bearer " + token)
            .contentType("application/json").content(json.writeValueAsString(Map.of("status", decision, "comment", "已核对", "version", 1))))
            .andReturn().getResponse().getStatus();
    }
}
