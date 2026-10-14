package com.kaoyan;

import com.kaoyan.common.PageResult;
import com.kaoyan.controller.DocumentController;
import com.kaoyan.controller.QuestionController;
import com.kaoyan.service.DocumentService;
import com.kaoyan.service.QuestionService;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import java.util.List;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class PageQueryBindingTest {
    @Test void adminQuestionPaginationAcceptsFrontendAndLegacyParameters() throws Exception {
        var service = mock(QuestionService.class);
        when(service.listPendingReview(anyInt(), anyInt())).thenReturn(PageResult.of(0, 1, 20, List.of()));
        var mvc = MockMvcBuilders.standaloneSetup(new QuestionController(service)).build();
        mvc.perform(get("/api/questions/admin/pending?pageNum=3&pageSize=25")).andExpect(status().isOk());
        verify(service).listPendingReview(3, 25);
        mvc.perform(get("/api/questions/admin/pending?page=2&size=15")).andExpect(status().isOk());
        verify(service).listPendingReview(2, 15);
    }

    @Test void documentStatusAndPaginationBindTogether() throws Exception {
        var service = mock(DocumentService.class);
        when(service.listByStatus(any(), anyInt(), anyInt())).thenReturn(PageResult.of(0, 1, 20, List.of()));
        var mvc = MockMvcBuilders.standaloneSetup(new DocumentController(service)).build();
        mvc.perform(get("/api/documents/admin/list?status=PENDING_REVIEW&pageNum=4&pageSize=30")).andExpect(status().isOk());
        verify(service).listByStatus("PENDING_REVIEW", 4, 30);
        mvc.perform(get("/api/documents/admin/list?page=2&size=5")).andExpect(status().isOk());
        verify(service).listByStatus(null, 2, 5);
    }
}
