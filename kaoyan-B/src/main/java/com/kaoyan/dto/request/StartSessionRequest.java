package com.kaoyan.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

/**
 * 开始刷题请求
 */
@Schema(description = "开始刷题请求")
public record StartSessionRequest(
        @Schema(description = "科目（可空）", example = "数据结构")
        String subject,

        @Schema(description = "难度（可空）", example = "EASY")
        String difficulty,

        @Schema(description = "题目数量", example = "5")
        @NotNull(message = "count 不能为空")
        @Min(value = 1, message = "count 至少为 1")
        Integer count
) {
}
