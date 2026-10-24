package com.kaoyan.config;

import lombok.Data;
import jakarta.validation.constraints.Min;
import org.springframework.validation.annotation.Validated;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@Validated
@ConfigurationProperties(prefix = "kaoyan.agent")
public class AgentProperties implements org.springframework.beans.factory.InitializingBean {
    private String baseUrl = "http://127.0.0.1:8001";
    @lombok.ToString.Exclude
    private String internalKey = "";
    private String quotaExemptUsername = "robin";
    private String sourcePolicyFile = "";
    @Min(1)
    private int dailyTaskLimit = 30;
    @Min(1)
    private int minuteTaskLimit = 6;

    @Override
    public void afterPropertiesSet() {
        // 使用通用异常，避免Bean校验诊断打印凭证的rejectedValue。
        if (internalKey == null || !internalKey.matches("[!-~]{16,}"))
            throw new IllegalStateException("AGENT_INTERNAL_KEY 需至少16位可打印ASCII字符");
    }
}
