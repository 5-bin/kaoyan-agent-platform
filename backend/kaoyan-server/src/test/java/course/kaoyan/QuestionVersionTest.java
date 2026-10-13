package course.kaoyan;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import course.kaoyan.catalog.*;
import course.kaoyan.common.exception.ApiException;
import course.kaoyan.pojo.entity.practice.*;
import course.kaoyan.practice.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.DefaultApplicationArguments;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties={"spring.datasource.url=jdbc:h2:mem:question-version-tests;MODE=PostgreSQL;DB_CLOSE_DELAY=-1",
    "spring.jpa.hibernate.ddl-auto=create-drop", "agent.internal-key=test-internal-key-123456789"})
@AutoConfigureMockMvc
@Transactional
class QuestionVersionTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @Autowired QuestionRepository questions;
    @Autowired QuestionVersionRepository versions;
    @Autowired QuestionVersionStore store;
    @Autowired QuestionVersionBootstrap bootstrap;
    @Autowired PracticeAttemptRepository attempts;
    @Autowired PracticeSessionRepository sessions;
    @Autowired PracticeSessionItemRepository items;

    private String login() throws Exception {
        String username = "v" + UUID.randomUUID().toString().replace("-", "").substring(0, 20);
        return mapper.readTree(mvc.perform(post("/api/auth/register").contentType("application/json")
            .content(mapper.writeValueAsString(Map.of("username", username, "password", "test-password"))))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString()).path("token").asText();
    }

    private Question question(boolean record) {
        Question q = questions.saveAndFlush(new Question(UUID.randomUUID().toString(), UUID.randomUUID().toString(),
            "data_structure", "easy", UUID.randomUUID().toString(), "版本测试知识点", "第一版题干",
            "第一版A", "第一版B", "第一版C", "第一版D", "B", "第一版解析", "第一版概念提示", "第一版思路提示",
            "第一版来源", "/references/demo-408.html#v1", "第一版第1题", 100));
        if (record) store.record(q);
        return q;
    }

    // Simulates an internal publisher. This phase deliberately exposes no public publish endpoint.
    private void nextVersion(Question q) {
        q.versionId = UUID.randomUUID().toString(); q.stem = "第二版题干"; q.correctOption = "A";
        q.optionA = "第二版A"; q.explanation = "第二版解析"; q.hintConcept = "第二版概念提示";
        q.hintApproach = "第二版思路提示"; q.sourceTitle = "第二版来源";
        q.sourceUrl = "/references/demo-408.html#v2"; q.sourceLocator = "第二版第1题";
        store.record(q);
        questions.saveAndFlush(q);
    }

    private JsonNode create(String token, Question q) throws Exception {
        return mapper.readTree(mvc.perform(post("/api/practice-sessions").header("Authorization", "Bearer " + token)
            .contentType("application/json").content(mapper.writeValueAsString(Map.of("mode", "chapter",
                "knowledgePointId", q.knowledgePointId, "questionCount", 1))))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
    }

    private String itemPath(JsonNode session) {
        return "/api/practice-sessions/" + session.path("id").asText() + "/items/"
            + session.path("items").get(0).path("id").asText();
    }

    private Map<String, Object> answer(Question q, String versionId, JsonNode session, String option) {
        Map<String, Object> body = new LinkedHashMap<>(Map.of("questionId", q.id, "questionVersionId", versionId,
            "selectedOption", option, "clientRequestId", UUID.randomUUID()));
        if (session != null) {
            body.put("sessionId", session.path("id").asText());
            body.put("sessionItemId", session.path("items").get(0).path("id").asText());
        }
        return body;
    }

    private JsonNode submit(String token, Map<String, Object> body) throws Exception {
        return mapper.readTree(mvc.perform(post("/api/attempts").header("Authorization", "Bearer " + token)
            .contentType("application/json").content(mapper.writeValueAsString(body)))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
    }

    @Test void oldBatchKeepsItsContentHintsDraftAndGradingWhenCurrentVersionChanges() throws Exception {
        String token = login(); Question q = question(true); String firstVersion = q.versionId;
        JsonNode oldSession = create(token, q);
        nextVersion(q);
        mvc.perform(get(itemPath(oldSession)).header("Authorization", "Bearer " + token))
            .andExpect(status().isOk()).andExpect(jsonPath("$.questionVersionId").value(firstVersion))
            .andExpect(jsonPath("$.stem").value("第一版题干")).andExpect(jsonPath("$.options.A").value("第一版A"))
            .andExpect(jsonPath("$.correctOption").doesNotExist()).andExpect(jsonPath("$.explanation").doesNotExist())
            .andExpect(jsonPath("$.hintConcept").doesNotExist());
        mvc.perform(put("/api/practice-sessions/" + oldSession.path("id").asText() + "/progress")
            .header("Authorization", "Bearer " + token).contentType("application/json")
            .content(mapper.writeValueAsString(Map.of("expectedRevision", 0, "currentOrdinal", 1,
                "drafts", List.of(Map.of("itemId", oldSession.path("items").get(0).path("id").asText(), "selectedOption", "B"))))))
            .andExpect(status().isOk());
        mvc.perform(get(itemPath(oldSession)).header("Authorization", "Bearer " + token))
            .andExpect(jsonPath("$.selectedOptionDraft").value("B"));
        for (int level = 1; level <= 2; level++) {
            mvc.perform(post(itemPath(oldSession) + "/hints").header("Authorization", "Bearer " + token)
                .contentType("application/json").content("{\"level\":" + level + "}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.content").value(level == 1 ? "第一版概念提示" : "第一版思路提示"));
        }
        JsonNode oldAnswer = submit(token, answer(q, firstVersion, oldSession, "B"));
        assertTrue(oldAnswer.path("correct").asBoolean());
        assertEquals(firstVersion, oldAnswer.path("questionVersionId").asText());
        assertEquals("第一版解析", oldAnswer.path("explanation").asText());
        assertEquals(2, oldAnswer.path("hintLevelUsed").asInt());
        JsonNode newSession = create(token, q);
        mvc.perform(get(itemPath(newSession)).header("Authorization", "Bearer " + token))
            .andExpect(jsonPath("$.questionVersionId").value(q.versionId)).andExpect(jsonPath("$.stem").value("第二版题干"));
        assertFalse(submit(token, answer(q, q.versionId, newSession, "B")).path("correct").asBoolean());
        mvc.perform(get("/api/practice-sessions/" + oldSession.path("id").asText() + "/result")
            .header("Authorization", "Bearer " + token)).andExpect(jsonPath("$.correct").value(1))
            .andExpect(jsonPath("$.accuracy").value(1.0));
    }

    @Test void completedHistoryAndIdempotentReplayKeepOldExplanationAndSources() throws Exception {
        String token = login(); Question q = question(true); String firstVersion = q.versionId;
        JsonNode session = create(token, q);
        Map<String, Object> body = answer(q, firstVersion, session, "B");
        JsonNode first = submit(token, body);
        nextVersion(q);
        assertEquals(first, submit(token, body));
        mvc.perform(get("/api/attempts/" + first.path("id").asText()).header("Authorization", "Bearer " + token))
            .andExpect(status().isOk()).andExpect(jsonPath("$.questionVersionId").value(firstVersion))
            .andExpect(jsonPath("$.explanation").value("第一版解析"))
            .andExpect(jsonPath("$.sourceTitle").value("第一版来源"))
            .andExpect(jsonPath("$.sourceUrl").value("/references/demo-408.html#v1"))
            .andExpect(jsonPath("$.sourceLocator").value("第一版第1题"));
        mvc.perform(get("/api/attempts").header("Authorization", "Bearer " + token))
            .andExpect(jsonPath("$.totalItems").value(1)).andExpect(jsonPath("$.items[0].questionVersionId").value(firstVersion));
        mvc.perform(get(itemPath(session)).header("Authorization", "Bearer " + token))
            .andExpect(jsonPath("$.explanation").value("第一版解析"));
        Map<String, Object> changedReplay = new LinkedHashMap<>(body);
        changedReplay.put("questionVersionId", q.versionId);
        mvc.perform(post("/api/attempts").header("Authorization", "Bearer " + token).contentType("application/json")
            .content(mapper.writeValueAsString(changedReplay))).andExpect(status().isConflict())
            .andExpect(jsonPath("$.code").value("REQUEST_CONFLICT"));
    }

    @Test void historicalVersionCannotBeUsedOutsideItsOwnedBatch() throws Exception {
        String token = login(); String other = login(); Question q = question(true); String firstVersion = q.versionId;
        JsonNode session = create(token, q);
        nextVersion(q);
        mvc.perform(post("/api/attempts").header("Authorization", "Bearer " + token).contentType("application/json")
            .content(mapper.writeValueAsString(answer(q, firstVersion, null, "B"))))
            .andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("QUESTION_VERSION_CHANGED"));
        mvc.perform(post("/api/attempts").header("Authorization", "Bearer " + token).contentType("application/json")
            .content(mapper.writeValueAsString(answer(q, q.versionId, session, "A"))))
            .andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("SESSION_QUESTION_MISMATCH"));
        mvc.perform(post("/api/attempts").header("Authorization", "Bearer " + other).contentType("application/json")
            .content(mapper.writeValueAsString(answer(q, firstVersion, session, "B"))))
            .andExpect(status().isNotFound());
        mvc.perform(get(itemPath(session)).header("Authorization", "Bearer " + other)).andExpect(status().isNotFound());
        assertTrue(submit(token, answer(q, q.versionId, null, "A")).path("correct").asBoolean());
    }

    @Test void repeatedSnapshotIsIdempotentAndReusingVersionIdForNewContentFails() {
        Question q = question(true); int before = versions.findAll().size();
        store.record(q);
        assertEquals(before, versions.findAll().size());
        q.explanation = "试图覆盖原解析";
        ApiException error = assertThrows(ApiException.class, () -> store.record(q));
        assertEquals(409, error.status);
        assertEquals("第一版解析", store.require(q.id, q.versionId).explanation);
    }

    @Test void versionCannotBeReadUnderAnotherQuestionId() {
        Question first = question(true); Question second = question(true);
        assertThrows(ApiException.class, () -> store.require(second.id, first.versionId));
    }

    @Test void missingSnapshotDoesNotFallBackToCurrentQuestionOrCreatePartialBatch() throws Exception {
        String token = login(); Question q = question(false); long before = sessions.count();
        mvc.perform(post("/api/practice-sessions").header("Authorization", "Bearer " + token)
            .contentType("application/json").content(mapper.writeValueAsString(Map.of("mode", "chapter",
                "knowledgePointId", q.knowledgePointId, "questionCount", 1))))
            .andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("QUESTION_VERSION_UNAVAILABLE"));
        // Snapshot preflight must run before any session is inserted (also observable in this transaction).
        assertEquals(before, sessions.count());
    }

    @Test void bootstrapPreservesLegacyIdsAndCanBeRepeated() {
        Question q = question(false);
        PracticeAttempt attempt = attempts.saveAndFlush(new PracticeAttempt(UUID.randomUUID().toString(), q.id,
            q.versionId, "B", true, UUID.randomUUID().toString(), null, null, 0));
        bootstrap.run(new DefaultApplicationArguments());
        int count = versions.findAll().size();
        bootstrap.run(new DefaultApplicationArguments());
        assertEquals(count, versions.findAll().size());
        assertEquals(q.versionId, attempts.findById(attempt.id).orElseThrow().questionVersionId);
        assertEquals("第一版解析", store.require(q.id, q.versionId).explanation);
    }

    @Test void bootstrapRejectsUnrecoverableHistoricalAttemptBeforeWritingSnapshots() {
        Question q = question(false);
        attempts.saveAndFlush(new PracticeAttempt(UUID.randomUUID().toString(), q.id, UUID.randomUUID().toString(),
            "B", true, UUID.randomUUID().toString(), null, null, 0));
        assertThrows(IllegalStateException.class, () -> bootstrap.run(new DefaultApplicationArguments()));
        assertTrue(versions.findById(q.versionId).isEmpty());
    }

    @Test void bootstrapRejectsUnrecoverableHistoricalBatchBeforeWritingSnapshots() {
        Question q = question(false);
        var session = sessions.saveAndFlush(new PracticeSession(UUID.randomUUID().toString(), "chapter",
            q.subject, q.knowledgePointId, q.difficulty, 1, 1));
        items.saveAndFlush(new PracticeSessionItem(session.id, 1, q.id, UUID.randomUUID().toString()));
        assertThrows(IllegalStateException.class, () -> bootstrap.run(new DefaultApplicationArguments()));
        assertTrue(versions.findById(q.versionId).isEmpty());
    }
}
