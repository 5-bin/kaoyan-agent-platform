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
    @MockitoBean AgentFeignClient agent;
    @MockitoBean StringRedisTemplate redis;

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
            r.setResult(Map.of("answer", "mock result")); return r;
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
}
