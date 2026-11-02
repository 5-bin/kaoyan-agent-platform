package com.kaoyan;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.common.ApiException;
import com.kaoyan.export.*;
import com.kaoyan.export.ExportContracts.*;
import com.kaoyan.learning.LearningProfiles;
import com.kaoyan.service.PersonalDocumentService;
import com.kaoyan.service.StudyStatService;
import com.kaoyan.service.TaskService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.data.redis.RedisConnectionFailureException;
import org.springframework.data.redis.core.StringRedisTemplate;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class ExportServiceTest {
    @Test void redisFailureDoesNotFallBackToAnUnscopedOrPermanentCache() {
        var redis = mock(StringRedisTemplate.class);
        when(redis.opsForValue()).thenThrow(new RedisConnectionFailureException("unavailable"));
        var cache = new ExportCache(redis, new ObjectMapper());
        ApiException error = assertThrows(ApiException.class, () -> cache.get(1, "00000000-0000-0000-0000-000000000000"));
        assertEquals(503, error.getHttpStatus());
    }
    @Test void noDataAndDisabledProfileAreExplicitRatherThanInvented() {
        var stats = mock(StudyStatService.class);
        when(stats.learning(1L, null, null, null)).thenReturn(Map.of("from", "2026-10-03", "to", "2026-11-01", "questionCount", 0,
                "correctCount", 0, "uniqueQuestions", 0, "wrongCount", 0, "daily", List.of(), "knowledgePoints", List.of()));
        @SuppressWarnings("unchecked") ObjectProvider<LearningProfiles> profiles = mock(ObjectProvider.class);
        var sources = new ExportSources(mock(PersonalDocumentService.class), stats, profiles,
                mock(TaskService.class), new ObjectMapper(), mock(ExportCharts.class));
        Content result = sources.build(1L, new Source("LEARNING_REPORT", null, null, null, null));
        assertTrue(result.markdown().contains("暂无有效作答"));
        assertTrue(result.markdown().contains("功能尚未启用"));
        assertTrue(result.markdown().contains("学习时长 | 未记录"));
        assertFalse(result.markdown().contains("正确率 | 0%"));
    }
    @Test void busyDownloadsAreBoundedAndLateClearedSourcesCannotReturnBytes() throws Exception {
        var sources = mock(ExportSources.class);
        var cache = mock(ExportCache.class);
        var renderer = mock(ExportRenderer.class);
        var preview = new Preview("snapshot", "note", "v1", "now", "later", "text", List.of());
        var source = new Source("NOTE", "note", 1, null, null);
        when(cache.get(1, "snapshot")).thenReturn(new Cached(Long.MAX_VALUE, source, preview));
        var entered = new CountDownLatch(2); var release = new CountDownLatch(1);
        when(renderer.render(preview, "pdf")).thenAnswer(call -> { entered.countDown(); release.await(5, TimeUnit.SECONDS); return new byte[]{1}; });
        var service = new ExportService(sources, cache, renderer);
        var pool = Executors.newFixedThreadPool(2);
        try {
            var first = pool.submit(() -> service.file(1, "snapshot", "pdf"));
            var second = pool.submit(() -> service.file(1, "snapshot", "pdf"));
            assertTrue(entered.await(5, TimeUnit.SECONDS));
            assertEquals(429, assertThrows(ApiException.class, () -> service.file(1, "snapshot", "pdf")).getHttpStatus());
            doThrow(new ApiException(404, "cleared")).when(sources).assertAvailable(1, source);
            release.countDown();
            assertThrows(java.util.concurrent.ExecutionException.class, () -> first.get(5, TimeUnit.SECONDS));
            assertThrows(java.util.concurrent.ExecutionException.class, () -> second.get(5, TimeUnit.SECONDS));
        } finally { release.countDown(); pool.shutdownNow(); }
    }
}
