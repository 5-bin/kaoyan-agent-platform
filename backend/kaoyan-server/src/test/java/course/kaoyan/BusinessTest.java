package course.kaoyan;

import course.kaoyan.pojo.entity.task.Task;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import course.kaoyan.auth.*;
import course.kaoyan.task.*;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.DefaultApplicationArguments;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties={"spring.datasource.url=jdbc:h2:mem:business-tests;MODE=PostgreSQL;DB_CLOSE_DELAY=-1", "spring.jpa.hibernate.ddl-auto=create-drop", "agent.internal-key=test-internal-key-123456789", "agent.daily-task-limit=3", "agent.minute-task-limit=100"})
@AutoConfigureMockMvc
class BusinessTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @Autowired AccountRepository accounts;
    @Autowired SessionRepository sessions;
    @Autowired TaskRepository tasks;
    @Autowired TaskService service;
    @MockitoBean AgentClient agent;

    private JsonNode register() throws Exception {
        String name = "u" + java.util.UUID.randomUUID().toString().replace("-", "").substring(0,20);
        return mapper.readTree(mvc.perform(post("/api/auth/register").contentType("application/json")
            .content(mapper.writeValueAsString(Map.of("username", name, "password", "test-password"))))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
    }
    private void successfulAgent() {
        when(agent.run(anyString(), anyString(), any(), any())).thenAnswer(call -> new AgentClient.Result(call.getArgument(0), "completed", "demo", "演示结果", List.of("检查"), List.of(), List.of(), 1));
    }
    private JsonNode submit(String token) throws Exception {
        return mapper.readTree(mvc.perform(post("/api/tasks").header("Authorization", "Bearer " + token)
            .contentType("application/json").content("{\"input\":\"请解释完整任务流程\"}"))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
    }
    @Test void passwordsAndTokensAreNotStoredInPlaintext() throws Exception {
        var login = register();
        var account = accounts.findById(login.path("user").path("id").asText()).orElseThrow();
        assertTrue(account.passwordHash.startsWith("$2"));
        assertNotEquals("test-password", account.passwordHash);
        assertTrue(sessions.findById(AuthService.hash(login.path("token").asText())).isPresent());
        assertTrue(sessions.findById(login.path("token").asText()).isEmpty());
    }
    @Test void loginAndWrongPassword() throws Exception {
        var login = register(); String name = login.path("user").path("username").asText();
        mvc.perform(post("/api/auth/login").contentType("application/json").content(mapper.writeValueAsString(Map.of("username", name, "password", "test-password")))).andExpect(status().isOk());
        mvc.perform(post("/api/auth/login").contentType("application/json").content(mapper.writeValueAsString(Map.of("username", name, "password", "wrong-password")))).andExpect(status().isUnauthorized());
    }
    @Test void duplicateUsernameIsRejected() throws Exception {
        var login = register();
        mvc.perform(post("/api/auth/register").contentType("application/json").content(mapper.writeValueAsString(Map.of("username", login.path("user").path("username").asText(), "password", "test-password")))).andExpect(status().isConflict());
    }
    @Test void guestCannotCreateOrListTasks() throws Exception {
        mvc.perform(get("/api/tasks")).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/tasks").contentType("application/json").content("{\"input\":\"example\"}")).andExpect(status().isUnauthorized());
    }
    @Test void taskResultIsPersistedAndReadable() throws Exception {
        successfulAgent(); var login = register(); String token = login.path("token").asText(); var task = submit(token);
        assertEquals("completed", task.path("status").asText());
        mvc.perform(get("/api/tasks/"+task.path("id").asText()).header("Authorization","Bearer "+token)).andExpect(status().isOk()).andExpect(jsonPath("$.result.answer").value("演示结果"));
        assertEquals("completed", tasks.findById(task.path("id").asText()).orElseThrow().status);
    }
    @Test void anotherAccountCannotReadTaskOrSeeHistory() throws Exception {
        successfulAgent(); var a = register(); var b = register(); var task = submit(a.path("token").asText());
        mvc.perform(get("/api/tasks/"+task.path("id").asText()).header("Authorization","Bearer "+b.path("token").asText())).andExpect(status().isNotFound());
        mvc.perform(get("/api/tasks").header("Authorization","Bearer "+b.path("token").asText())).andExpect(jsonPath("$.totalItems").value(0));
    }
    @Test void invalidAndForgedInputNeverCallsAgent() throws Exception {
        var login = register(); String token = login.path("token").asText();
        for (String input : List.of("{\"input\":\"   \"}", "{\"input\":\"ok\",\"ownerId\":\"someone\"}", "{\"input\":\"" + "a".repeat(8001) + "\"}")) {
            mvc.perform(post("/api/tasks").header("Authorization","Bearer "+token).contentType("application/json").content(input)).andExpect(status().isBadRequest());
        }
        verifyNoInteractions(agent);
    }
    @Test void offlineAgentBecomesSavedFailure() throws Exception {
        when(agent.run(anyString(),anyString(),any(),any())).thenThrow(new RuntimeException("private-secret"));
        var login = register(); var task = submit(login.path("token").asText());
        assertEquals("failed", task.path("status").asText());
        assertFalse(task.toString().contains("private-secret"));
        assertEquals("failed", tasks.findById(task.path("id").asText()).orElseThrow().status);
    }
    @Test void dailyLimitStopsFurtherCalls() throws Exception {
        successfulAgent(); var login = register(); String token = login.path("token").asText();
        for(int i=0;i<3;i++) submit(token);
        mvc.perform(post("/api/tasks").header("Authorization","Bearer "+token).contentType("application/json").content("{\"input\":\"请解释完整任务流程\"}"))
            .andExpect(status().isTooManyRequests()).andExpect(jsonPath("$.code").value("DAILY_LIMIT"));
        verify(agent,times(3)).run(anyString(),anyString(),any(),any());
    }
    @Test void expiredAndLoggedOutSessionsCannotAccessTasks() throws Exception {
        var login = register(); String token = login.path("token").asText();
        mvc.perform(post("/api/auth/logout").header("Authorization","Bearer "+token)).andExpect(status().isOk());
        mvc.perform(get("/api/tasks").header("Authorization","Bearer "+token)).andExpect(status().isUnauthorized());
        var other = register(); String expired = other.path("token").asText();
        var session = sessions.findById(AuthService.hash(expired)).orElseThrow(); session.expiresAt=Instant.now().minusSeconds(1); sessions.save(session);
        mvc.perform(get("/api/tasks").header("Authorization","Bearer "+expired)).andExpect(status().isUnauthorized());
    }
    @Test void restartMarksInterruptedTasksFailed() throws Exception {
        var login = register(); var pending = tasks.saveAndFlush(new Task(login.path("user").path("id").asText(),"中断的任务"));
        service.run(new DefaultApplicationArguments());
        assertEquals("failed",tasks.findById(pending.id).orElseThrow().status);
    }
    @Test void invalidPaginationRejected() throws Exception {
        var login=register(); mvc.perform(get("/api/tasks?page=-1").header("Authorization","Bearer "+login.path("token").asText())).andExpect(status().isBadRequest());
    }
    @Test void minuteLimitPreventsSecondModelCall() throws Exception {
        successfulAgent(); var login=register();
        var limited=new TaskService(tasks,agent,mapper,30,1);
        String owner=login.path("user").path("id").asText(); limited.create(owner,"请解释完整任务流程");
        var error=assertThrows(course.kaoyan.common.exception.ApiException.class,()->limited.create(owner,"请再次解释完整任务流程"));
        assertEquals(429,error.status); assertEquals("RATE_LIMIT",error.code);
        verify(agent,times(1)).run(anyString(),anyString(),any(),any());
    }
    @Test void needsInputIsSavedAsItsOwnStatus() throws Exception {
        when(agent.run(anyString(),anyString(),any(),any())).thenAnswer(call -> new AgentClient.Result(call.getArgument(0),"needs_input","demo","请补充目标",List.of(),List.of(),List.of("目标是什么？"),1));
        var login=register(); var task=submit(login.path("token").asText());
        assertEquals("needs_input",task.path("status").asText());
        assertEquals("目标是什么？",task.path("result").path("followUp").get(0).asText());
    }
    @Test void publicHealthAndFrontendAreAvailable() throws Exception {
        mvc.perform(get("/api/health")).andExpect(status().isOk()).andExpect(jsonPath("$.service").value("java-business"));
        mvc.perform(get("/index.html")).andExpect(status().isOk());
    }

    @Test void registrationCannotGrantAdminAndStudentCannotUseManagement() throws Exception {
        var login = register(); String token = login.path("token").asText();
        assertEquals("student", login.path("user").path("role").asText());
        mvc.perform(get("/api/admin/documents").header("Authorization", "Bearer " + token))
            .andExpect(status().isForbidden()).andExpect(jsonPath("$.code").value("FORBIDDEN"));
        mvc.perform(post("/api/auth/register").contentType("application/json")
            .content("{\"username\":\"forged_admin\",\"password\":\"test-password\",\"role\":\"admin\"}"))
            .andExpect(status().isBadRequest());
    }

    @Test void authenticatedPendingProfileStudyAndRecommendationReturn501AndNeverCreateTasks() throws Exception {
        var login=register(); String token=login.path("token").asText(); long before=tasks.count();
        mvc.perform(get("/api/profile").header("Authorization","Bearer "+token))
            .andExpect(status().isNotImplemented()).andExpect(jsonPath("$.code").value("FEATURE_NOT_IMPLEMENTED"));
        mvc.perform(get("/api/study/summary").header("Authorization","Bearer "+token))
            .andExpect(status().isNotImplemented()).andExpect(jsonPath("$.code").value("FEATURE_NOT_IMPLEMENTED"));
        mvc.perform(post("/api/tasks").header("Authorization","Bearer "+token).contentType("application/json")
            .content("{\"taskType\":\"school_recommendation\",\"input\":\"请根据档案推荐专业\"}"))
            .andExpect(status().isNotImplemented());
        assertEquals(before,tasks.count()); verifyNoInteractions(agent);
    }

    @Test void malformedPracticeInputIsRejectedBefore501() throws Exception {
        var login=register(); String token=login.path("token").asText();
        for (String body:List.of("{\"mode\":\"random\",\"questionCount\":0}",
                "{\"mode\":\"invented\"}", "{\"mode\":\"random\",\"ownerId\":\"someone\"}")) {
            mvc.perform(post("/api/practice-sessions").header("Authorization","Bearer "+token)
                .contentType("application/json").content(body)).andExpect(status().isBadRequest());
        }
    }

    @Test void serverSideAdminRoleStillGetsExplicitPendingResponse() throws Exception {
        var login=register(); var account=accounts.findById(login.path("user").path("id").asText()).orElseThrow();
        account.role="admin"; accounts.saveAndFlush(account);
        mvc.perform(get("/api/admin/documents").header("Authorization","Bearer "+login.path("token").asText()))
            .andExpect(status().isNotImplemented());
    }

    @Test void typedTaskIsPersistedAndUnknownSubjectRejected() throws Exception {
        successfulAgent(); var login=register(); String token=login.path("token").asText();
        mvc.perform(post("/api/tasks").header("Authorization","Bearer "+token).contentType("application/json")
            .content("{\"input\":\"请解释进程与线程的区别\",\"taskType\":\"knowledge_qa\",\"subject\":\"operating_system\"}"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.taskType").value("knowledge_qa"))
            .andExpect(jsonPath("$.resultSchemaVersion").value(2));
        mvc.perform(get("/api/tasks?taskType=knowledge_qa").header("Authorization","Bearer "+token))
            .andExpect(jsonPath("$.totalItems").value(1));
        mvc.perform(post("/api/tasks").header("Authorization","Bearer "+token).contentType("application/json")
            .content("{\"input\":\"请解释这道问题\",\"subject\":\"finance\"}"))
            .andExpect(status().isBadRequest());
    }
}


