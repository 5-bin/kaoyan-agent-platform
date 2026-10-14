package com.kaoyan.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.kaoyan.entity.User;

/**
 * 用户 Service
 */
public interface UserService extends IService<User> {

    /**
     * 注册
     *
     * @param username   用户名
     * @param rawPassword 原始密码
     * @return 新用户
     */
    User register(String username, String rawPassword);

    /**
     * 登录，返回 access token
     *
     * @param username   用户名
     * @param rawPassword 原始密码
     * @return access token
     */
    String login(String username, String rawPassword);

    /**
     * 用 refresh token 换新的 access token
     *
     * @param refreshToken refresh token
     * @return 新的 access token
     */
    String refresh(String refreshToken);

    /**
     * 登出，把当前 token 的 jti 写入黑名单
     *
     * @param authorizationHeader Authorization 头
     */
    void logout(String authorizationHeader);

    /**
     * 更新档案
     *
     * @param userId       用户 ID
     * @param avatarUrl    头像 URL（空则不动）
     * @param targetSchool 目标院校
     * @param targetMajor  目标专业
     * @param examYear     考试年份
     * @param background   考生背景
     */
    void updateProfile(Long userId, String avatarUrl, String targetSchool,
                       String targetMajor, Integer examYear, String background);

    /**
     * 更新头像
     *
     * @param userId    用户 ID
     * @param avatarUrl 头像 URL
     */
    void updateAvatar(Long userId, String avatarUrl);

    /**
     * 按用户名查用户
     *
     * @param username 用户名
     * @return 用户
     */
    User findByUsername(String username);

    /**
     * 启用 / 禁用账号
     *
     * @param userId 用户 ID
     * @param status 状态
     */
    void changeStatus(Long userId, Integer status);

    /**
     * 修改角色
     *
     * @param userId 用户 ID
     * @param role   角色
     */
    void changeRole(Long userId, String role);
}
