package com.kaoyan.service;

import java.util.Locale;
import java.util.Objects;
import java.util.regex.Pattern;

/** Shared topic comparison for learning reads, previews and current-version validation. */
final class LearningTopic {
    private LearningTopic() {}

    private static String normalize(Object value) {
        return Objects.toString(value, "").replaceAll("\\s+", "").toUpperCase(Locale.ROOT)
            .replace("传输控制协议", "TCP").replace("用户数据报协议", "UDP")
            .replace("TCP协议", "TCP").replace("UDP协议", "UDP");
    }

    static boolean matches(String requested, Object actual) {
        if (requested == null) return true;
        String topic = normalize(requested), point = normalize(actual);
        if (topic.isBlank()) return false;
        String left = topic.matches("^[A-Z0-9].*") ? "(?<![A-Z0-9])" : "";
        String right = topic.matches(".*[A-Z0-9]$") ? "(?![A-Z0-9])" : "";
        return Pattern.compile(left + Pattern.quote(topic) + right).matcher(point).find();
    }
}
