package com.kaoyan.controller;

import com.kaoyan.common.Result;
import com.kaoyan.dto.request.LoginRequest;
import com.kaoyan.dto.request.RefreshRequest;
import com.kaoyan.dto.request.RegisterRequest;
import com.kaoyan.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 认证接口
 */
@Tag(name = "01. 认证", description = "注册、登录、刷新、登出")
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
@SecurityRequirements
public class AuthController {

    private final UserService userService;

    /**
     * 注册
     */
    @Operation(summary = "注册", description = "用户名唯一，密码 6-32 位")
    @PostMapping("/register")
    public Result<?> register(@Valid @RequestBody RegisterRequest req) {
        return Result.ok(userService.register(req.username(), req.password()));
    }

    /**
     * 登录
     */
    @Operation(summary = "登录", description = "返回 accessToken")
    @PostMapping("/login")
    public Result<Map<String, String>> login(@Valid @RequestBody LoginRequest req) {
        String access = userService.login(req.username(), req.password());
        return Result.ok(Map.of("accessToken", access));
    }

    /**
     * 刷新 Token
     */
    @Operation(summary = "刷新 Token")
    @PostMapping("/refresh")
    public Result<Map<String, String>> refresh(@Valid @RequestBody RefreshRequest req) {
        return Result.ok(Map.of("accessToken",
                userService.refresh(req.refreshToken())));
    }

    /**
     * 登出
     */
    @Operation(summary = "登出", description = "把当前 Token 的 jti 写入黑名单")
    @PostMapping("/logout")
    public Result<Void> logout(@RequestHeader("Authorization") String authorization) {
        userService.logout(authorization);
        return Result.ok();
    }
}
