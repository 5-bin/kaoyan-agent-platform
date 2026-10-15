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

    @Test void deletionUsesGuardedTaskOperationAndPreservesItsErrors() {
        var tasks = mock(TaskService.class);
        var service = new RecommendServiceImpl(tasks);
        service.delete("ended", 1L);
        verify(tasks).hideRecommendation(1L, "ended");
        doThrow(new ApiException(409, "任务尚未结束")).when(tasks).hideRecommendation(1L, "owned");
        assertEquals(409, assertThrows(ApiException.class, () -> service.delete("owned", 1L)).getHttpStatus());
        doThrow(new ApiException(404, "推荐记录不存在")).when(tasks).hideRecommendation(1L, "owned");
        assertEquals(404, assertThrows(ApiException.class, () -> service.delete("owned", 1L)).getHttpStatus());
        verify(tasks, never()).removeById(anyString());
    }
}
