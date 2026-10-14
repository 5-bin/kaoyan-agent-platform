package com.kaoyan.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

/**
 * 更新头像请求
 */
@Schema(description = "更新头像请求")
public record AvatarRequest(
        @Schema(description = "头像 URL", example = "https://example.com/avatar.png")
        @NotBlank(message = "avatarUrl 不能为空")
        String avatarUrl
) {
}
