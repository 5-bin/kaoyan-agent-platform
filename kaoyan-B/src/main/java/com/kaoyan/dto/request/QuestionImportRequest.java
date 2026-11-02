package com.kaoyan.dto.request;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.List;

/** Nested entries are validated by the service so errors identify the one-based question index. */
public record QuestionImportRequest(
    @NotNull @Size(min=1, max=50, message="每批请导入1至50道题目") List<QuestionEntryRequest> questions
) {}
