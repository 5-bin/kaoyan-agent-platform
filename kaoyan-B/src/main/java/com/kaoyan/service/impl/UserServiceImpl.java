package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.common.ApiException;
import com.kaoyan.entity.User;
import com.kaoyan.mapper.UserMapper;
import com.kaoyan.security.JwtService;
import com.kaoyan.service.UserService;
import io.jsonwebtoken.Claims;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Date;

/**
 * 用户 Service 实现
 */
@Service
@RequiredArgsConstructor
public class UserServiceImpl extends ServiceImpl<UserMapper, User> implements UserService {

    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;

    @Override
    @Transactional
    public User register(String username, String rawPassword) {
        String name = username == null ? "" : username.trim();
        if (name.isEmpty()) {
            throw new ApiException(400, 400, "用户名不能为空");
        }
        if (rawPassword == null || rawPassword.length() < 6 || rawPassword.length() > 32) {
            throw new ApiException(400, 400, "密码长度需为 6-32 位");
        }
        if (findByUsername(name) != null) {
            throw new ApiException(409, 409, "用户名已存在");
        }
        User u = new User();
        u.setUsername(name);
        u.setPasswordHash(passwordEncoder.encode(rawPassword));
        u.setRole("STUDENT");
        u.setStatus(1);
        save(u);
        u.setPasswordHash(null);
        return u;
    }

    @Override
    public String login(String username, String rawPassword) {
        User u = findByUsername(username == null ? "" : username.trim());
        if (u == null || u.getPasswordHash() == null
                || !passwordEncoder.matches(rawPassword, u.getPasswordHash())) {
            throw new ApiException(401, 401, "用户名或密码错误");
        }
        if (u.getStatus() == null || u.getStatus() != 1) {
            throw new ApiException(403, 403, "账号已禁用");
        }
        return jwtService.generateAccess(u);
    }

    @Override
    public String refresh(String refreshToken) {
        Claims c = jwtService.parse(refreshToken);
        if (!"refresh".equals(c.get("type", String.class))) {
            throw new ApiException(401, 401, "refresh Token 无效");
        }
        User u = getById(Long.valueOf(c.getSubject()));
        if (u == null || u.getStatus() == null || u.getStatus() != 1) {
            throw new ApiException(401, 401, "用户不存在或已禁用");
        }
        return jwtService.generateAccess(u);
    }

    @Override
    public void logout(String authorizationHeader) {
        if (authorizationHeader == null || !authorizationHeader.startsWith("Bearer ")) {
            return;
        }
        try {
            Claims c = jwtService.parse(authorizationHeader.substring(7));
            Date exp = c.getExpiration();
            long ttl = exp == null ? 0 : (exp.getTime() - System.currentTimeMillis()) / 1000;
            jwtService.revoke(c.getId(), ttl);
        } catch (ApiException ignored) {
        }
    }

    @Override
    @Transactional
    public void updateProfile(Long userId, String avatarUrl, String targetSchool,
                              String targetMajor, Integer examYear, String background) {
        User u = getById(userId);
        if (u == null) {
            throw new ApiException(404, 404, "用户不存在");
        }
        if (avatarUrl != null && !avatarUrl.isBlank()) {
            u.setAvatarUrl(avatarUrl);
        }
        u.setTargetSchool(targetSchool);
        u.setTargetMajor(targetMajor);
        u.setExamYear(examYear);
        u.setBackground(background);
        updateById(u);
    }

    @Override
    @Transactional
    public void updateAvatar(Long userId, String avatarUrl) {
        User u = getById(userId);
        if (u == null) {
            throw new ApiException(404, 404, "用户不存在");
        }
        u.setAvatarUrl(avatarUrl);
        updateById(u);
    }

    @Override
    public User findByUsername(String username) {
        return lambdaQuery().eq(User::getUsername, username).one();
    }

    @Override
    @Transactional
    public void changeStatus(Long userId, Integer status) {
        User u = getById(userId);
        if (u == null) {
            throw new ApiException(404, 404, "用户不存在");
        }
        u.setStatus(status);
        updateById(u);
    }

    @Override
    @Transactional
    public void changeRole(Long userId, String role) {
        User u = getById(userId);
        if (u == null) {
            throw new ApiException(404, 404, "用户不存在");
        }
        u.setRole(role);
        updateById(u);
    }
}
