package com.kaoyan;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.dto.agent.AgentRequest;
import com.kaoyan.dto.agent.AgentResponse;
import com.kaoyan.feign.AgentFeignClient;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import java.util.Map;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.url=jdbc:h2:mem:framework;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER",
    "spring.datasource.username=sa", "spring.datasource.password=",
    "spring.sql.init.mode=always", "spring.sql.init.schema-locations=classpath:schema-test.sql",
    "jwt.secret=test-only-jwt-key-at-least-32-characters",
    "kaoyan.agent.internal-key=test-only-internal-key-12345"
})
@AutoConfigureMockMvc
class FrameworkIntegrationTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @Autowired org.springframework.jdbc.core.JdbcTemplate jdbc;
    @Autowired com.kaoyan.security.JwtService jwt;
    @Autowired com.kaoyan.service.impl.TaskServiceImpl taskService;
    @Autowired com.kaoyan.config.AgentProperties agentProps;
    @Autowired com.kaoyan.mapper.TaskMapper taskMapper;
    @MockitoBean AgentFeignClient agent;
    @MockitoBean StringRedisTemplate redis;

    @Test void clearingAllDuringSynchronousRequestCannotRestoreItsPrivatePayload() throws Exception {
        String token=login();long owner=Long.parseLong(jwt.parse(token).getSubject());
        var entered=new java.util.concurrent.CountDownLatch(1);var release=new java.util.concurrent.CountDownLatch(1);
        when(agent.chat(anyString(),any())).thenAnswer(call -> {
            AgentRequest request=call.getArgument(1);entered.countDown();assertTrue(release.await(10,java.util.concurrent.TimeUnit.SECONDS));
            var response=new AgentResponse();response.setTaskId(request.getTaskId());response.setStatus("SUCCESS");
            response.setReleaseId("rag-v1-1234567890abcdef");response.setReferences(java.util.List.of());
            response.setResult(Map.of("answer","SYNTHETIC_PRIVATE_ANSWER","outcome","COMPLETED","resolvedTaskType","KNOWLEDGE_QA","releaseId",response.getReleaseId(),"explanationMode","rules"));return response;
        });
        var pool=java.util.concurrent.Executors.newSingleThreadExecutor();
        try {
            var future=pool.submit(() -> mvc.perform(post("/api/tasks").header("Authorization","Bearer "+token).contentType("application/json")
                .content("{\"taskType\":\"KNOWLEDGE_QA\",\"input\":{\"query\":\"SYNTHETIC_PRIVATE_QUERY\"}}"))
                .andReturn().getResponse().getContentAsString());
            assertTrue(entered.await(10,java.util.concurrent.TimeUnit.SECONDS));
            mvc.perform(delete("/api/conversations").header("Authorization","Bearer "+token)).andExpect(status().isOk());
            release.countDown();String body=future.get(10,java.util.concurrent.TimeUnit.SECONDS);
            assertFalse(body.contains("SYNTHETIC_PRIVATE"));
            var rows=jdbc.queryForList("SELECT input_payload,result_payload,status FROM task WHERE user_id=?",owner);
            assertEquals(1,rows.size());assertNull(rows.get(0).get("input_payload"));assertNull(rows.get(0).get("result_payload"));
            assertEquals("CANCELLED",rows.get(0).get("status"));
        } finally {release.countDown();pool.shutdownNow();}
    }

    @Test void expiredHiddenRecommendationsAreErasedRatherThanOnlyHidden() throws Exception {
        String token=login();long owner=Long.parseLong(jwt.parse(token).getSubject());String id=UUID.randomUUID().toString();
        jdbc.update("INSERT INTO task(id,user_id,task_type,status,input_payload,result_payload,created_at,deleted_at) VALUES(?,?,'SCHOOL_RECOMMEND','SUCCESS','{\"query\":\"SYNTHETIC_HIDDEN\"}','{\"answer\":\"SYNTHETIC_HIDDEN\"}',?,CURRENT_TIMESTAMP)",id,owner,java.time.LocalDateTime.now().minusDays(31));
        mvc.perform(get("/api/tasks").header("Authorization","Bearer "+token)).andExpect(status().isOk());
        assertNull(jdbc.queryForObject("SELECT input_payload FROM task WHERE id=?",String.class,id));
        assertNull(jdbc.queryForObject("SELECT result_payload FROM task WHERE id=?",String.class,id));
    }

    String login() throws Exception {
        String username = "t" + UUID.randomUUID().toString().substring(0, 8);
        String body = mapper.writeValueAsString(Map.of("username", username, "password", "test-password"));
        mvc.perform(post("/api/auth/register").contentType("application/json").content(body)).andExpect(status().isOk());
        return mapper.readTree(mvc.perform(post("/api/auth/login").contentType("application/json").content(body))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString()).path("data").path("accessToken").asText();
    }

    @Test void authenticatedTaskPersistsAndIsIsolatedByOwner() throws Exception {
        when(agent.chat(anyString(), any())).thenAnswer(call -> {
            AgentRequest req = call.getArgument(1);
            var r = new AgentResponse(); r.setTaskId(req.getTaskId()); r.setStatus("SUCCESS");
            r.setReleaseId("rag-v1-1234567890abcdef"); r.setReferences(java.util.List.of());
            r.setResult(Map.of("answer", "mock result", "outcome", "UNSUPPORTED", "resolvedTaskType", "KNOWLEDGE_QA",
                "releaseId", r.getReleaseId(), "explanationMode", "rules")); return r;
        });
        String token = login(); String other = login();
        String text = mvc.perform(post("/api/tasks").header("Authorization", "Bearer " + token)
                .contentType("application/json").content("{\"taskType\":\"KNOWLEDGE_QA\",\"input\":{\"query\":\"解释进程\"}}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.status").value("SUCCESS"))
                .andReturn().getResponse().getContentAsString();
        String id = mapper.readTree(text).path("data").path("id").asText();
        mvc.perform(get("/api/tasks/" + id).header("Authorization", "Bearer " + token))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.resultPayload.answer").value("mock result"));
        mvc.perform(get("/api/tasks/" + id).header("Authorization", "Bearer " + other)).andExpect(status().isNotFound());
        mvc.perform(get("/api/tasks").header("Authorization", "Bearer " + other))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.total").value(0));
    }

    @Test void malformedJsonAndForgedFieldsAre400BeforeAgentCall() throws Exception {
        String token = login();
        for (String body : new String[]{"{", "{\"taskType\":\"CHAT\",\"userId\":2,\"input\":{\"query\":\"q\"}}",
                "{\"taskType\":\"invented\",\"input\":{\"query\":\"q\"}}"}) {
            mvc.perform(post("/api/tasks").header("Authorization", "Bearer " + token)
                    .contentType("application/json").content(body)).andExpect(status().isBadRequest());
        }
        verifyNoInteractions(agent);
    }

    @Test void logoutActuallyRevokesAccess() throws Exception {
        var values = mock(ValueOperations.class); when(redis.opsForValue()).thenReturn(values);
        doAnswer(call -> {
            when(redis.hasKey(call.getArgument(0))).thenReturn(true); return null;
        }).when(values).set(anyString(), anyString(), anyLong(), any());
        String token = login();
        mvc.perform(post("/api/auth/logout").header("Authorization", "Bearer " + token)).andExpect(status().isOk());
        mvc.perform(get("/api/tasks").header("Authorization", "Bearer " + token)).andExpect(status().isUnauthorized());
    }

    @Test void taskPaginationUsesDatabaseTotal() throws Exception {
        String token = login();
        long owner = Long.parseLong(jwt.parse(token).getSubject());
        for (int i = 0; i < 25; i++) {
            jdbc.update("INSERT INTO task(id,user_id,task_type,status,input_payload,created_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)",
                    UUID.randomUUID().toString(), owner, "KNOWLEDGE_QA", "RUNNING", "{\"query\":\"test\"}");
        }
        mvc.perform(get("/api/tasks?pageNum=2&pageSize=20").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.total").value(25))
                .andExpect(jsonPath("$.data.page").value(2)).andExpect(jsonPath("$.data.list.length()").value(5));
    }

    @Test void invalidUpstreamResponseIsSavedAsFailure() throws Exception {
        when(agent.chat(anyString(), any())).thenThrow(new RuntimeException("private-upstream-detail"));
        String token = login();
        String text = mvc.perform(post("/api/tasks").header("Authorization", "Bearer " + token)
                .contentType("application/json").content("{\"taskType\":\"KNOWLEDGE_QA\",\"input\":{\"query\":\"解释进程\"}}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.status").value("FAILED"))
                .andReturn().getResponse().getContentAsString();
        assertFalse(text.contains("private-upstream-detail"));
        String id = mapper.readTree(text).path("data").path("id").asText();
        mvc.perform(get("/api/tasks/" + id).header("Authorization", "Bearer " + token))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.status").value("FAILED"));
    }

    @Test void summaryRejectsForeignAndIncompleteSessionBeforeCreatingTasks() throws Exception {
        String token = login();
        long owner = Long.parseLong(jwt.parse(token).getSubject());
        jdbc.update("INSERT INTO practice_record(user_id,session_id,question_id,is_correct,grading_status) VALUES(?,?,?,?,?)",
                owner, "unfinished-" + owner, 1, null, "valid");
        mvc.perform(post("/api/practice/sessions/foreign/ai-summary").header("Authorization", "Bearer " + token))
                .andExpect(status().isNotFound());
        mvc.perform(post("/api/practice/sessions/unfinished-" + owner + "/ai-summary").header("Authorization", "Bearer " + token))
                .andExpect(status().isConflict());
        mvc.perform(get("/api/tasks").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.total").value(0));
        verifyNoInteractions(agent);
    }

    @Test void restartMarksInterruptedPersistedTasksFailed() throws Exception {
        String token = login();
        long owner = Long.parseLong(jwt.parse(token).getSubject());
        String id = UUID.randomUUID().toString();
        jdbc.update("INSERT INTO task(id,user_id,task_type,status,input_payload,created_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)",
                id, owner, "KNOWLEDGE_QA", "RUNNING", "{\"query\":\"interrupted\"}");
        taskService.run(new org.springframework.boot.DefaultApplicationArguments());
        mvc.perform(get("/api/tasks/" + id).header("Authorization", "Bearer " + token))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.status").value("FAILED"));
        assertEquals("FAILED", jdbc.queryForObject("SELECT status FROM task WHERE id=?", String.class, id));
    }

    @Test void persistedDailyAndMinuteQuotasRejectWithoutCallingAgent() throws Exception {
        for (int count : new int[]{30, 6}) {
            String token = login();
            long owner = Long.parseLong(jwt.parse(token).getSubject());
            for (int i = 0; i < count; i++) {
                jdbc.update("INSERT INTO task(id,user_id,task_type,status,input_payload,created_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)",
                        UUID.randomUUID().toString(), owner, "KNOWLEDGE_QA", "FAILED", "{\"query\":\"quota-test\"}");
            }
            mvc.perform(post("/api/tasks").header("Authorization", "Bearer " + token)
                    .contentType("application/json").content("{\"taskType\":\"KNOWLEDGE_QA\",\"input\":{\"query\":\"解释进程\"}}"))
                    .andExpect(status().isTooManyRequests());
            assertEquals(count, jdbc.queryForObject("SELECT COUNT(*) FROM task WHERE user_id=?", Integer.class, owner));
        }
        verifyNoInteractions(agent);
    }

    @Test void deletingSuccessfulOrFailedRecommendationNeverRestoresDailyOrMinuteQuota() throws Exception {
        int daily = agentProps.getDailyTaskLimit(), minute = agentProps.getMinuteTaskLimit();
        try {
            for (boolean dailyLimit : new boolean[]{true, false}) {
                agentProps.setDailyTaskLimit(dailyLimit ? 1 : 100);
                agentProps.setMinuteTaskLimit(dailyLimit ? 100 : 1);
                for (boolean failed : new boolean[]{false, true}) {
                    doAnswer(call -> {
                        if (failed) throw new RuntimeException("test-only failure");
                        AgentRequest req = call.getArgument(1);
                        var response = new AgentResponse(); response.setTaskId(req.getTaskId()); response.setStatus("SUCCESS");
                        response.setReleaseId("rag-v1-1234567890abcdef"); response.setReferences(java.util.List.of());
                        response.setResult(Map.of("answer", "rule result", "outcome", "UNSUPPORTED",
                            "resolvedTaskType", "SCHOOL_RECOMMEND", "explanationMode", "rules", "releaseId", response.getReleaseId()));
                        return response;
                    }).when(agent).chat(anyString(), any());
                    String token = login();
                    long owner = Long.parseLong(jwt.parse(token).getSubject());
                    String body = "{\"query\":\"compare programs\"}";
                    JsonNode created = mapper.readTree(mvc.perform(post("/api/recommends/generate")
                        .header("Authorization", "Bearer " + token).contentType("application/json").content(body))
                        .andExpect(status().isOk()).andExpect(jsonPath("$.data.status").value(failed ? "FAILED" : "SUCCESS"))
                        .andExpect(jsonPath("$.data.deletedAt").doesNotExist()).andReturn().getResponse().getContentAsString()).path("data");
                    String id = created.path("id").asText();
                    mvc.perform(post("/api/recommends/generate").header("Authorization", "Bearer " + token)
                        .contentType("application/json").content(body)).andExpect(status().isTooManyRequests());
                    mvc.perform(delete("/api/recommends/" + id).header("Authorization", "Bearer " + token)).andExpect(status().isOk());
                    mvc.perform(post("/api/recommends/generate").header("Authorization", "Bearer " + token)
                        .contentType("application/json").content(body)).andExpect(status().isTooManyRequests());
                    assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM task WHERE user_id=?", Integer.class, owner));
                    assertNotNull(jdbc.queryForObject("SELECT deleted_at FROM task WHERE id=?", java.sql.Timestamp.class, id));
                    if (!failed) assertNotNull(jdbc.queryForObject("SELECT result_payload FROM task WHERE id=?", String.class, id));
                    mvc.perform(get("/api/tasks").header("Authorization", "Bearer " + token))
                        .andExpect(status().isOk()).andExpect(jsonPath("$.data.total").value(0)).andExpect(jsonPath("$.data.list.length()").value(0));
                    mvc.perform(get("/api/recommends").header("Authorization", "Bearer " + token))
                        .andExpect(status().isOk()).andExpect(jsonPath("$.data.length()").value(0));
                    mvc.perform(get("/api/tasks/" + id).header("Authorization", "Bearer " + token)).andExpect(status().isNotFound());
                    mvc.perform(delete("/api/recommends/" + id).header("Authorization", "Bearer " + token)).andExpect(status().isNotFound());
                }
            }
            verify(agent, times(4)).chat(anyString(), any());
        } finally {
            agentProps.setDailyTaskLimit(daily); agentProps.setMinuteTaskLimit(minute);
        }
    }

    @Test void recommendationDeletionChecksOwnerTypeAndTerminalStatus() throws Exception {
        String token = login(), other = login();
        long owner = Long.parseLong(jwt.parse(token).getSubject());
        for (String state : new String[]{"RUNNING", "PENDING", "SUCCESS"}) {
            String id = UUID.randomUUID().toString();
            jdbc.update("INSERT INTO task(id,user_id,task_type,status,created_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)",
                id, owner, "SCHOOL_RECOMMEND", state);
            mvc.perform(delete("/api/recommends/" + id).header("Authorization", "Bearer " + other)).andExpect(status().isNotFound());
            mvc.perform(delete("/api/recommends/" + id).header("Authorization", "Bearer " + token))
                .andExpect(state.equals("SUCCESS") ? status().isOk() : status().isConflict());
            assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM task WHERE id=?", Integer.class, id));
        }
        String id = UUID.randomUUID().toString();
        jdbc.update("INSERT INTO task(id,user_id,task_type,status,created_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)",
            id, owner, "KNOWLEDGE_QA", "SUCCESS");
        mvc.perform(delete("/api/recommends/" + id).header("Authorization", "Bearer " + token)).andExpect(status().isNotFound());
        mvc.perform(get("/api/tasks/" + id).header("Authorization", "Bearer " + token)).andExpect(status().isOk());
        verifyNoInteractions(agent);
    }

    @Test void missingOrEmptySnapshotsRejectWholeSummaryWithoutSpendingQuota() throws Exception {
        String token = login();
        long owner = Long.parseLong(jwt.parse(token).getSubject());
        for (String session : new String[]{"legacy", "mixed", "empty"}) {
            jdbc.update("INSERT INTO practice_record(user_id,session_id,question_id,is_correct,grading_status,question_snapshot) VALUES(?,?,?,?,?,?)",
                owner, session, 1, 0, "valid", session.equals("empty") ? "{}" : null);
            if (session.equals("mixed")) jdbc.update(
                "INSERT INTO practice_record(user_id,session_id,question_id,is_correct,grading_status,question_snapshot) VALUES(?,?,?,?,?,?)",
                owner, session, 2, 1, "valid", mapper.writeValueAsString(Map.of("id", 2, "version", 1, "subject", "操作系统", "content", "题干", "answer", "A")));
            mvc.perform(post("/api/practice/sessions/" + session + "/ai-summary").header("Authorization", "Bearer " + token))
                .andExpect(status().isConflict()).andExpect(jsonPath("$.message").value("该批次包含缺少题目版本快照的历史作答，暂不支持生成总结"));
        }
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM task WHERE user_id=?", Integer.class, owner));
        verifyNoInteractions(agent);
    }

    @Test void guardedDeletionAndConcurrentRequestsKeepTheOriginalRow() throws Exception {
        String token = login();
        long owner = Long.parseLong(jwt.parse(token).getSubject());
        String id = UUID.randomUUID().toString();
        jdbc.update("INSERT INTO task(id,user_id,task_type,status,created_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)",
            id, owner, "KNOWLEDGE_QA", "RUNNING");
        var now = java.time.LocalDateTime.now();
        assertEquals(0, taskMapper.hideRecommendation(owner, id, now));
        jdbc.update("UPDATE task SET task_type='SCHOOL_RECOMMEND' WHERE id=?", id);
        assertEquals(0, taskMapper.hideRecommendation(owner, id, now));
        jdbc.update("UPDATE task SET status='SUCCESS' WHERE id=?", id);
        assertEquals(0, taskMapper.hideRecommendation(owner + 100000, id, now));
        var executor = java.util.concurrent.Executors.newFixedThreadPool(2);
        try {
            java.util.concurrent.Callable<Integer> hide = () -> {
                try { taskService.hideRecommendation(owner, id); return 200; }
                catch (com.kaoyan.common.ApiException e) { return e.getHttpStatus(); }
            };
            var results = executor.invokeAll(java.util.List.of(hide, hide));
            assertEquals(java.util.Set.of(200, 404), java.util.Set.of(results.get(0).get(), results.get(1).get()));
        } finally { executor.shutdownNow(); }
        assertEquals(0, taskMapper.hideRecommendation(owner, id, now));
        assertNotNull(jdbc.queryForObject("SELECT deleted_at FROM task WHERE id=?", java.sql.Timestamp.class, id));
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM task WHERE id=?", Integer.class, id));
    }
}
