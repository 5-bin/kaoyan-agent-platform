package com.kaoyan.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

/**
 * 审核请求
 */
@Schema(description = "审核请求")
public record ReviewRequest(
        @Schema(description = "审核结果", example = "APPROVED")
        @NotBlank(message = "status 不能为空")
        String status,

        @Schema(description = "审核意见")
        String comment
) {
}
