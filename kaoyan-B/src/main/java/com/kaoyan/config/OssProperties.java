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
    private String accessKeyId;

    /** AccessKey Secret */
    private String accessKeySecret;

    /** Bucket 名称 */
    private String bucketName;

    /** 访问 URL 前缀 */
    private String urlPrefix;
}
