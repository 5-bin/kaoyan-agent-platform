package com.kaoyan.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * JWT 配置
 */
@Data
@Component
@ConfigurationProperties(prefix = "jwt")
public class JwtProperties {

    /** 签名密钥，长度至少 32 字节 */
    private String secret;

    /** access token 有效期（分钟） */
    private long accessExpireMinutes = 60;

    /** refresh token 有效期（天） */
    private long refreshExpireDays = 14;

    /** 签发者 */
    private String issuer = "kaoyan-agent";
}
