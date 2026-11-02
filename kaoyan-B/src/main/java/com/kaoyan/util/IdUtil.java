package com.kaoyan.util;

import java.util.UUID;

/**
 * ID 生成工具
 */
public final class IdUtil {

    private IdUtil() {
    }

    /**
     * 32 位无横线 UUID
     *
     * @return 32 位字符串
     */
    public static String uuid() {
        return UUID.randomUUID().toString().replace("-", "");
    }

    /**
     * 标准 UUID 格式（含横线）
     *
     * @return UUID 字符串
     */
    public static String sessionId() {
        return UUID.randomUUID().toString();
    }

    /** Managed sessions keep their route prefix and fit the existing VARCHAR(36) column. */
    public static String managedSessionId() {
        return "L-" + uuid();
    }
}
