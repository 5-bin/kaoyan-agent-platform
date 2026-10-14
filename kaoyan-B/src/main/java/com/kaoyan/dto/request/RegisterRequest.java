package com.kaoyan.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 注册请求
 */
@Schema(description = "注册请求")
public record RegisterRequest(
        @Schema(description = "用户名", example = "student")
        @NotBlank(message = "用户名不能为空")
        String username,

        @Schema(description = "密码，6-32 位", example = "password")
        @NotBlank(message = "密码不能为空")
        @Size(min = 6, max = 32, message = "密码长度需为 6-32 位")
        String password
) {
}
