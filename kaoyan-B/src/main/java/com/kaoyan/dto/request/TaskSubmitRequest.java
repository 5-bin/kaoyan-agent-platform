package com.kaoyan.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.util.Map;

/**
 * 提交任务请求
 */
@Schema(description = "提交任务请求")
public record TaskSubmitRequest(
        @Schema(description = "任务类型", example = "KNOWLEDGE_QA")
        @NotBlank(message = "taskType 不能为空")
        @Pattern(regexp = "KNOWLEDGE_QA|SCHOOL_RECOMMEND|PRACTICE_SUMMARY|CHAT|WRONG_QUESTION_TUTOR", message = "未知任务类型")
        String taskType,

        @Schema(description = "输入参数")
        @Size(max = 4) Map<String, Object> input
) {
}
