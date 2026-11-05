package com.kaoyan.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 阿里云 OSS 配置（全部从环境变量读取）
 */
@Data
@Component
@ConfigurationProperties(prefix = "oss")
public class OssProperties {

    /** OSS 端点 */
    private String endpoint;

    /** AccessKey ID */
    @lombok.ToString.Exclude
    private String accessKeyId;

    /** AccessKey Secret */
    @lombok.ToString.Exclude
    private String accessKeySecret;

    /** Bucket 名称 */
    private String bucketName;

    /** 访问 URL 前缀 */
    private String urlPrefix;

    /** Object namespace; empty preserves existing local object keys. */
    private String keyPrefix = "";

    /** Validate and normalize a namespace without reflecting configuration values. */
    public String normalizedKeyPrefix() {
        if (keyPrefix == null || keyPrefix.isEmpty()) return "";
        String value = keyPrefix.endsWith("/") ? keyPrefix.substring(0, keyPrefix.length() - 1) : keyPrefix;
        if (value.length() > 128 || !value.matches("[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*")) {
            throw new IllegalStateException("OSS_KEY_PREFIX 格式无效");
        }
        return value + "/";
    }
}
