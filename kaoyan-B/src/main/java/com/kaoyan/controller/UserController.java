package com.kaoyan.controller;

import com.kaoyan.common.Result;
import com.kaoyan.dto.request.AvatarRequest;
import com.kaoyan.dto.request.ProfileRequest;
import com.kaoyan.entity.User;
import com.kaoyan.security.UserContext;
import com.kaoyan.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

/**
 * 用户接口
 */
@Tag(name = "11. 用户", description = "头像与档案")
@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    /**
     * 更新头像
     */
    @Operation(summary = "更新头像", description = "先调 /api/files/upload 拿 URL，再传到这里")
    @PutMapping("/avatar")
    public Result<Void> updateAvatar(@Valid @RequestBody AvatarRequest req) {
        userService.updateAvatar(UserContext.currentUserId(), req.avatarUrl());
        return Result.ok();
    }

    /**
     * 更新档案
     */
    @Operation(summary = "更新档案")
    @PutMapping("/profile")
    public Result<Void> updateProfile(@Valid @RequestBody ProfileRequest req) {
        userService.updateProfile(UserContext.currentUserId(),
                req.avatarUrl(), req.targetSchool(), req.targetMajor(),
                req.examYear(), req.background());
        return Result.ok();
    }

    /**
     * 当前用户信息
     */
    @Operation(summary = "当前用户信息")
    @GetMapping("/me")
    public Result<User> me() {
        return Result.ok(userService.getById(UserContext.currentUserId()));
    }
}
