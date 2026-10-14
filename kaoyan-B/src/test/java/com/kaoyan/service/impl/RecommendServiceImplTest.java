package com.kaoyan.service.impl;

import com.kaoyan.common.ApiException;
import com.kaoyan.entity.Task;
import com.kaoyan.service.TaskService;
import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class RecommendServiceImplTest {
    @Test void recommendationDelegatesToCanonicalTaskPipelineWithoutPlaceholderWrites() {
        var tasks = mock(TaskService.class);
        var service = new RecommendServiceImpl(tasks);
        var input = Map.<String,Object>of("query", "推荐院校", "preferences", Map.of("degreeType", "academic"));
        var result = new Task(); result.setId("recommend-task");
        when(tasks.submit(1L, "SCHOOL_RECOMMEND", input)).thenReturn(result);
        assertSame(result, service.generate(1L, input));
        verify(tasks).submit(1L, "SCHOOL_RECOMMEND", input);
        verifyNoMoreInteractions(tasks);
    }

    @Test void cannotDeleteRunningOrNonRecommendationTasks() {
        var tasks = mock(TaskService.class);
        var service = new RecommendServiceImpl(tasks);
        var task = new Task(); task.setTaskType("SCHOOL_RECOMMEND"); task.setStatus("RUNNING");
        when(tasks.detail(1L, "owned")).thenReturn(task);
        assertEquals(409, assertThrows(ApiException.class, () -> service.delete("owned", 1L)).getHttpStatus());
        task.setTaskType("KNOWLEDGE_QA");
        assertEquals(404, assertThrows(ApiException.class, () -> service.delete("owned", 1L)).getHttpStatus());
        verify(tasks, never()).removeById(anyString());
    }
}
