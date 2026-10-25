package com.kaoyan.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Size;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Pattern;
import java.util.List;

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
        @Max(value = 50, message = "count 最多为 50") Integer count,
        @Pattern(regexp = "NORMAL|WRONG|FAVORITE", message = "source 无效") String source,
        @Size(max = 50) List<@NotNull @Positive Long> questionIds
) {
    public StartSessionRequest(String subject, String difficulty, Integer count) {
        this(subject, difficulty, count, "NORMAL", null);
    }
}
