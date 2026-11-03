package com.kaoyan.controller;

import com.kaoyan.common.Result;
import com.kaoyan.common.ApiException;
import com.kaoyan.util.OssUtil;
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
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

/**
 * 用户接口
 */
@Tag(name = "11. 用户", description = "头像与档案")
@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;
    private final OssUtil ossUtil;

    private void validateAvatar(Long userId, String avatarUrl) {
        User current = userService.getById(userId);
        if (current == null) throw new ApiException(404, 404, "用户不存在");
        if (!ossUtil.isAllowedAvatar(avatarUrl, userId, current.getAvatarUrl())) {
            throw new ApiException(400, 400, "头像地址无效");
        }
    }

    /**
     * 更新头像
     */
    @Operation(summary = "更新头像", description = "先调 /api/files/upload 拿 URL，再传到这里")
    @PutMapping("/avatar")
    public Result<Void> updateAvatar(@Valid @RequestBody AvatarRequest req) {
        Long userId = UserContext.currentUserId();
        validateAvatar(userId, req.avatarUrl());
        userService.updateAvatar(userId, req.avatarUrl());
        return Result.ok();
    }

    /**
     * 更新档案
     */
    @Operation(summary = "更新档案")
    @PutMapping("/profile")
    public Result<Void> updateProfile(@Valid @RequestBody ProfileRequest req) {
        Long userId = UserContext.currentUserId();
        validateAvatar(userId, req.avatarUrl());
        userService.updateProfile(userId,
                req.avatarUrl(), req.targetSchool(), req.targetMajor(),
                req.examYear(), req.degreeType(), req.background());
        return Result.ok();
    }

    /** 读取当前账号头像，避免公开私有存储链接。 */
    @GetMapping("/avatar/content")
    public ResponseEntity<byte[]> avatarContent() {
        User user = userService.getById(UserContext.currentUserId());
        if (user == null || user.getAvatarUrl() == null) throw new ApiException(404, 404, "头像不存在");
        byte[] content = ossUtil.readAvatar(user.getAvatarUrl());
        String url = user.getAvatarUrl().toLowerCase(java.util.Locale.ROOT);
        MediaType type = url.endsWith(".png") ? MediaType.IMAGE_PNG
                : url.endsWith(".gif") ? MediaType.IMAGE_GIF
                : url.endsWith(".webp") ? MediaType.parseMediaType("image/webp") : MediaType.IMAGE_JPEG;
        return ResponseEntity.ok().header(HttpHeaders.CACHE_CONTROL, "no-store")
                .contentType(type).body(content);
    }

    /**
     * 当前用户信息
     */
    @Operation(summary = "当前用户信息")
    @GetMapping("/me")
    public Result<User> me() {
        User user = userService.getById(UserContext.currentUserId());
        if (user == null) throw new ApiException(404, 404, "用户不存在");
        return Result.ok(user);
    }
}
