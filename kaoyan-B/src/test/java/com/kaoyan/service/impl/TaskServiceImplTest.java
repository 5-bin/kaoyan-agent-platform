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

    @BeforeEach void setup() {
        var assistant = new MapperBuilderAssistant(new MybatisConfiguration(), "test");
        assistant.setCurrentNamespace("test");
        TableInfoHelper.initTableInfo(assistant, Task.class);
        TableInfoHelper.initTableInfo(assistant, PracticeRecord.class);
        service = spy(new TaskServiceImpl(agent, new AgentProperties(), mock(UserMapper.class), records));
        ReflectionTestUtils.setField(service, "baseMapper", tasks);
        doAnswer(call -> { ((Task) call.getArgument(0)).setId("task-1"); return true; }).when(service).save(any(Task.class));
        doReturn(true).when(service).updateById(any(Task.class));
    }

    @Test void malformedInputDoesNotCreateTaskOrCallAgent() {
        for (var input : List.<Map<String,Object>>of(Map.of(), Map.of("query", 12), Map.of("query", " "),
                Map.of("query", "q", "userId", 2), Map.of("query", "q".repeat(8001)))) {
            assertEquals(400, assertThrows(ApiException.class, () -> service.submit(1L, "KNOWLEDGE_QA", input)).getHttpStatus());
        }
        assertThrows(ApiException.class, () -> service.submit(1L, "invented", Map.of("query", "q")));
        verify(service, never()).save(any(Task.class)); verifyNoInteractions(agent);
    }

    @Test void foreignOrMissingSessionRejectedBeforeTaskCreation() {
        when(records.selectList(any())).thenReturn(List.of());
        assertEquals(404, assertThrows(ApiException.class,
            () -> service.submit(1L, "PRACTICE_SUMMARY", Map.of("sessionId", "foreign"))).getHttpStatus());
        verify(service, never()).save(any(Task.class)); verifyNoInteractions(agent);
    }

    @Test void incompleteSessionRejected() {
        var record = new PracticeRecord(); record.setGradingStatus("valid"); record.setQuestionId(3L);
        when(records.selectList(any())).thenReturn(List.of(record));
        assertEquals(409, assertThrows(ApiException.class,
            () -> service.submit(1L, "PRACTICE_SUMMARY", Map.of("sessionId", "session-1"))).getHttpStatus());
        verifyNoInteractions(agent);
    }

    @Test void successfulResultSavedAndResponseIdentityChecked() {
        var response = response("task-1", Map.of("answer", "mock answer"));
        when(agent.chat(anyString(), any())).thenReturn(response);
        var saved = service.submit(1L, "KNOWLEDGE_QA", Map.of("query", "进程是什么"));
        assertEquals("SUCCESS", saved.getStatus());
        assertEquals("mock answer", saved.getResultPayload().get("answer"));
        verify(service).updateById(saved);
        response.setTaskId("someone-else");
        assertEquals("FAILED", service.submit(1L, "KNOWLEDGE_QA", Map.of("query", "q")).getStatus());
    }

    @Test void invalidResultAndExceptionsBecomeSanitizedSavedFailures() {
        when(agent.chat(anyString(), any())).thenReturn(response("task-1", "not-an-object"));
        assertEquals("FAILED", service.submit(1L, "KNOWLEDGE_QA", Map.of("query", "q")).getStatus());
        when(agent.chat(anyString(), any())).thenThrow(new RuntimeException("private-upstream-detail"));
        var saved = service.submit(1L, "KNOWLEDGE_QA", Map.of("query", "q"));
        assertEquals("FAILED", saved.getStatus());
        assertFalse(saved.getErrorMessage().contains("private-upstream-detail"));
        verify(service, times(2)).updateById(any(Task.class));
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
        verify(service, never()).save(any(Task.class));
        verifyNoInteractions(agent);
    }

    @Test void utcDayCutoffIsConvertedToTheStoredLocalDateTimeZone() {
        var clock = java.time.Clock.fixed(java.time.Instant.parse("2026-10-14T00:30:00Z"), java.time.ZoneId.of("Asia/Shanghai"));
        ReflectionTestUtils.setField(service, "clock", clock);
        when(agent.chat(anyString(), any())).thenReturn(response("task-1", Map.of("answer", "mock")));
        service.submit(1L, "KNOWLEDGE_QA", Map.of("query", "q"));
        verify(tasks).countForUserSince(1L, java.time.LocalDateTime.parse("2026-10-14T08:00:00"));
        verify(tasks).countForUserSince(1L, java.time.LocalDateTime.parse("2026-10-14T08:29:00"));
    }

    private AgentResponse response(String id, Object result) {
        var r = new AgentResponse(); r.setTaskId(id); r.setStatus("SUCCESS"); r.setResult(result); return r;
    }
}
