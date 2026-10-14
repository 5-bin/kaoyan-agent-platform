package com.kaoyan.util;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/**
 * 时间格式化工具
 */
public final class DateUtil {

    /** 日期格式 */
    public static final String DATE_PATTERN = "yyyy-MM-dd";

    /** 日期时间格式 */
    public static final String DATETIME_PATTERN = "yyyy-MM-dd HH:mm:ss";

    private static final DateTimeFormatter DATE_FMT = DateTimeFormatter.ofPattern(DATE_PATTERN);
    private static final DateTimeFormatter DATETIME_FMT = DateTimeFormatter.ofPattern(DATETIME_PATTERN);

    private DateUtil() {
    }

    /**
     * 格式化 LocalDateTime
     *
     * @param dt 时间
     * @return 格式化字符串
     */
    public static String format(LocalDateTime dt) {
        return dt == null ? null : dt.format(DATETIME_FMT);
    }

    /**
     * 格式化 LocalDate
     *
     * @param d 日期
     * @return 格式化字符串
     */
    public static String format(LocalDate d) {
        return d == null ? null : d.format(DATE_FMT);
    }
}
