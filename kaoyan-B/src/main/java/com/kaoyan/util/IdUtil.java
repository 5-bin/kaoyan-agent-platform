package com.kaoyan.util;

import java.util.UUID;

/**
 * ID 生成工具
 */
public final class IdUtil {

    private static final String BASE62 =
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

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
     * 8 位 base62 短 ID
     *
     * @return 8 位字符串
     */
    public static String shortId() {
        UUID u = UUID.randomUUID();
        long n = u.getMostSignificantBits() ^ u.getLeastSignificantBits();
        StringBuilder sb = new StringBuilder(8);
        for (int i = 0; i < 8; i++) {
            sb.append(BASE62.charAt((int) Math.floorMod(n, 62)));
            n /= 62;
        }
        return sb.toString();
    }

    /**
     * 标准 UUID 格式（含横线）
     *
     * @return UUID 字符串
     */
    public static String sessionId() {
        return UUID.randomUUID().toString();
    }
}
