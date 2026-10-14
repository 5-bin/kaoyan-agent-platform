package com.kaoyan.config;

import lombok.Data;
import jakarta.validation.constraints.Min;
import org.springframework.validation.annotation.Validated;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * JWT 配置
 */
@Data
@Component
@Validated
@ConfigurationProperties(prefix = "jwt")
public class JwtProperties implements org.springframework.beans.factory.InitializingBean {

    /** 签名密钥，长度至少 32 字节 */
    @lombok.ToString.Exclude
    private String secret = "";

    /** access token 有效期（分钟） */
    @Min(1)
    private long accessExpireMinutes = 60;

    /** refresh token 有效期（天） */
    @Min(1)
    private long refreshExpireDays = 14;

    /** 签发者 */
    private String issuer = "kaoyan-agent";

    @Override
    public void afterPropertiesSet() {
        if (secret == null || secret.length() < 32)
            throw new IllegalStateException("JWT_SECRET 需至少32字符");
    }
}
