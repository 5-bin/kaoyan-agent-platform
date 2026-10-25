package com.kaoyan.service.impl;

import com.kaoyan.common.ApiException;
import com.kaoyan.config.AgentProperties;
import com.kaoyan.dto.agent.AgentResponse;
import com.kaoyan.entity.Task;
import com.kaoyan.entity.PracticeRecord;
import com.kaoyan.feign.AgentFeignClient;
import com.kaoyan.mapper.*;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import java.util.List;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class TaskServiceImplTest {
    AgentFeignClient agent = mock(AgentFeignClient.class);
    PracticeRecordMapper records = mock(PracticeRecordMapper.class);
    TaskMapper tasks = mock(TaskMapper.class);
    TaskServiceImpl service;
    TaskStore store;

    @BeforeEach void setup() {
        var assistant = new MapperBuilderAssistant(new MybatisConfiguration(), "test");
        assistant.setCurrentNamespace("test");
        TableInfoHelper.initTableInfo(assistant, Task.class);
        TableInfoHelper.initTableInfo(assistant, PracticeRecord.class);
        var users = mock(UserMapper.class);
        var user = new com.kaoyan.entity.User(); user.setId(1L);
        when(users.selectById(1L)).thenReturn(user);
        store = new TaskStore(tasks, new AgentProperties());
        service = spy(new TaskServiceImpl(agent, new AgentProperties(), users, records, mock(QuestionMapper.class), store,
            new WrongQuestionTutorContext(records, tasks),
            new com.kaoyan.service.ReferenceSourcePolicy(new AgentProperties(), new com.fasterxml.jackson.databind.ObjectMapper())));
        ReflectionTestUtils.setField(service, "baseMapper", tasks);
        when(tasks.insert(any(Task.class))).thenReturn(1);
        when(tasks.updateById(any(Task.class))).thenReturn(1);
    }

    @Test void malformedInputDoesNotCreateTaskOrCallAgent() {
        for (var input : List.<Map<String,Object>>of(Map.of(), Map.of("query", 12), Map.of("query", " "),
                Map.of("query", "q", "userId", 2), Map.of("query", "q".repeat(8001)))) {
            assertEquals(400, assertThrows(ApiException.class, () -> service.submit(1L, "KNOWLEDGE_QA", input)).getHttpStatus());
        }
        assertThrows(ApiException.class, () -> service.submit(1L, "invented", Map.of("query", "q")));
        verify(tasks, never()).insert(any(Task.class)); verifyNoInteractions(agent);
    }

    @Test void foreignOrMissingSessionRejectedBeforeTaskCreation() {
        when(records.selectList(any())).thenReturn(List.of());
        assertEquals(404, assertThrows(ApiException.class,
            () -> service.submit(1L, "PRACTICE_SUMMARY", Map.of("sessionId", "foreign"))).getHttpStatus());
        verify(tasks, never()).insert(any(Task.class)); verifyNoInteractions(agent);
    }

    @Test void incompleteSessionRejected() {
        var record = new PracticeRecord(); record.setGradingStatus("valid"); record.setQuestionId(3L);
        when(records.selectList(any())).thenReturn(List.of(record));
        assertEquals(409, assertThrows(ApiException.class,
            () -> service.submit(1L, "PRACTICE_SUMMARY", Map.of("sessionId", "session-1"))).getHttpStatus());
        verifyNoInteractions(agent);
    }

    @Test void successfulResultSavedAndResponseIdentityChecked() {
        when(agent.chat(anyString(), any())).thenAnswer(call -> response(
            ((com.kaoyan.dto.agent.AgentRequest) call.getArgument(1)).getTaskId(), Map.of("answer", "mock answer")));
        var saved = service.submit(1L, "KNOWLEDGE_QA", Map.of("query", "进程是什么"));
        assertEquals("SUCCESS", saved.getStatus());
        assertEquals("mock answer", saved.getResultPayload().get("answer"));
        verify(tasks).updateById(saved);
        doReturn(response("someone-else", Map.of("answer", "mock"))).when(agent).chat(anyString(), any());
        assertEquals("FAILED", service.submit(1L, "KNOWLEDGE_QA", Map.of("query", "q")).getStatus());
    }

    @Test void invalidResultAndExceptionsBecomeSanitizedSavedFailures() {
        when(agent.chat(anyString(), any())).thenAnswer(call -> response(
            ((com.kaoyan.dto.agent.AgentRequest) call.getArgument(1)).getTaskId(), "not-an-object"));
        assertEquals("FAILED", service.submit(1L, "KNOWLEDGE_QA", Map.of("query", "q")).getStatus());
        doThrow(new RuntimeException("private-upstream-detail")).when(agent).chat(anyString(), any());
        var saved = service.submit(1L, "KNOWLEDGE_QA", Map.of("query", "q"));
        assertEquals("FAILED", saved.getStatus());
        assertFalse(saved.getErrorMessage().contains("private-upstream-detail"));
        verify(tasks, times(2)).updateById(any(Task.class));
    }

    @Test void foreignTaskLooksLikeMissingTask() {
        var task = new Task(); task.setUserId(2L);
        doReturn(task).when(service).getById("private");
        assertEquals(404, assertThrows(ApiException.class, () -> service.detail(1L, "private")).getHttpStatus());
    }

    @Test void savedDailyAndMinuteCountsBlockCallsBeforeCreatingMoreTasks() {
        when(tasks.countForUserSince(eq(1L), any())).thenReturn(30L);
        assertEquals(429, assertThrows(ApiException.class,
                () -> service.submit(1L, "KNOWLEDGE_QA", Map.of("query", "q"))).getHttpStatus());
        when(tasks.countForUserSince(eq(1L), any())).thenReturn(0L, 6L);
        assertEquals(429, assertThrows(ApiException.class,
                () -> service.submit(1L, "KNOWLEDGE_QA", Map.of("query", "q"))).getHttpStatus());
        verify(tasks, never()).insert(any(Task.class));
        verifyNoInteractions(agent);
    }

    @Test void utcDayCutoffIsConvertedToTheStoredLocalDateTimeZone() {
        var clock = java.time.Clock.fixed(java.time.Instant.parse("2026-10-14T00:30:00Z"), java.time.ZoneId.of("Asia/Shanghai"));
        ReflectionTestUtils.setField(store, "clock", clock);
        when(agent.chat(anyString(), any())).thenReturn(response("task-1", Map.of("answer", "mock")));
        service.submit(1L, "KNOWLEDGE_QA", Map.of("query", "q"));
        verify(tasks).countForUserSince(1L, java.time.LocalDateTime.parse("2026-10-14T08:00:00"));
        verify(tasks).countForUserSince(1L, java.time.LocalDateTime.parse("2026-10-14T08:29:00"));
    }

    private AgentResponse response(String id, Object result) {
        var r = new AgentResponse(); r.setTaskId(id); r.setStatus("SUCCESS");
        r.setReleaseId("rag-v1-1234567890abcdef"); r.setReferences(List.of());
        if (result instanceof Map<?, ?> map) {
            var body = new java.util.HashMap<String,Object>();
            map.forEach((key, value) -> body.put(key.toString(), value));
            body.put("outcome", "UNSUPPORTED"); body.put("resolvedTaskType", "KNOWLEDGE_QA");
            body.put("releaseId", r.getReleaseId()); body.put("explanationMode", "rules");
            r.setResult(body);
        } else r.setResult(result);
        return r;
    }
}
