package com.kaoyan.service.impl;

import com.kaoyan.entity.Task;
import com.kaoyan.mapper.PracticeRecordMapper;
import com.kaoyan.mapper.TaskMapper;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import java.time.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class WrongQuestionTutorHistoryTest {
    @Test void historyUsesOriginalCutoffAndStopsAtInvisibleOrInconsistentSources() {
        var mapper=mock(TaskMapper.class);var context=new WrongQuestionTutorContext(mock(PracticeRecordMapper.class),mapper);
        var clock=Clock.fixed(Instant.parse("2026-10-29T00:00:00Z"),ZoneOffset.UTC);
        ReflectionTestUtils.setField(context,"clock",clock);
        Map<String,Object> attempt=Map.of("id",3,"version",2,"recordId",7,"answer","B");
        Task parent=new Task();parent.setId("parent");parent.setUserId(1L);parent.setTaskType("WRONG_QUESTION_TUTOR");parent.setStatus("SUCCESS");
        parent.setCreatedAt(LocalDateTime.now(clock).minusDays(30));parent.setResultPayload(Map.of("answer","source-answer"));
        parent.setInputPayload(Map.of("recordId",7,"query","source-query","attempt",attempt,"messages",List.of(Map.of("content","untrusted-embedded"))));
        when(mapper.selectById("parent")).thenReturn(parent);
        Task current=new Task();current.setUserId(1L);current.setTaskType("WRONG_QUESTION_TUTOR");
        current.setInputPayload(Map.of("recordId",7,"query","new-query","attempt",attempt,"parentTaskId","parent"));
        assertEquals(2,context.turn(current).messages().size());
        assertFalse(context.turn(current).toString().contains("untrusted-embedded"));
        parent.setCreatedAt(parent.getCreatedAt().minusNanos(1));assertTrue(context.turn(current).messages().isEmpty());
        parent.setCreatedAt(LocalDateTime.now(clock));parent.setDeletedAt(LocalDateTime.now(clock));assertTrue(context.turn(current).messages().isEmpty());
        parent.setDeletedAt(null);parent.setUserId(2L);assertTrue(context.turn(current).messages().isEmpty());
        parent.setUserId(1L);parent.setStatus("FAILED");assertTrue(context.turn(current).messages().isEmpty());
        parent.setStatus("SUCCESS");parent.setInputPayload(Map.of("recordId",8,"query","wrong-record","attempt",attempt));assertTrue(context.turn(current).messages().isEmpty());
    }
}
