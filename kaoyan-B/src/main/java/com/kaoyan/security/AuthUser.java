package com.kaoyan.security;

/**
 * 登录用户 principal
 *
 * @param id       用户 ID
 * @param username 用户名
 * @param role     角色
 */
public record AuthUser(Long id, String username, String role) {
}
