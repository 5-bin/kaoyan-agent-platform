package com.kaoyan.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

import java.util.Map;

/**
 * 提交任务请求
 */
@Schema(description = "提交任务请求")
public record TaskSubmitRequest(
        @Schema(description = "任务类型", example = "KNOWLEDGE_QA")
        @NotBlank(message = "taskType 不能为空")
        String taskType,

        @Schema(description = "输入参数")
        Map<String, Object> input
) {
}
