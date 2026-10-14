package com.kaoyan.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

/**
 * 刷新 Token 请求
 */
@Schema(description = "刷新 Token 请求")
public record RefreshRequest(
        @Schema(description = "refresh token")
        @NotBlank(message = "refreshToken 不能为空")
        String refreshToken
) {
}
