package com.kaoyan.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/**
 * 作答请求
 */
@Schema(description = "作答请求")
public record AnswerRequest(
        @Schema(description = "题目 ID", example = "1")
        @NotNull(message = "questionId 不能为空")
        Long questionId,

        @Schema(description = "用户答案", example = "B")
        @NotBlank(message = "answer 不能为空")
        String answer
) {
}
