package com.kaoyan.security;

import com.kaoyan.common.ApiException;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

/**
 * 从 SecurityContext 读取当前登录用户
 */
public final class UserContext {

    private UserContext() {
    }

    /**
     * 当前登录用户 ID，未登录抛 401
     *
     * @return 用户 ID
     */
    public static Long currentUserId() {
        return current().id();
    }

    /**
     * 当前登录用户名
     *
     * @return 用户名
     */
    public static String currentUsername() {
        return current().username();
    }

    /**
     * 当前登录用户角色
     *
     * @return 角色
     */
    public static String currentRole() {
        return current().role();
    }

    private static AuthUser current() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof AuthUser au)) {
            throw new ApiException(401, 401, "未登录");
        }
        return au;
    }
}
