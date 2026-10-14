package com.kaoyan.service.impl;

import com.kaoyan.common.ApiException;
import com.kaoyan.mapper.RecommendRecordMapper;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class RecommendServiceImplTest {
    @Test void pendingRecommendationDoesNotWritePlaceholderRecords() {
        var mapper = mock(RecommendRecordMapper.class);
        var service = new RecommendServiceImpl();
        ReflectionTestUtils.setField(service, "baseMapper", mapper);
        assertEquals(501, assertThrows(ApiException.class, () -> service.generate(1L)).getHttpStatus());
        verifyNoInteractions(mapper);
    }
}
