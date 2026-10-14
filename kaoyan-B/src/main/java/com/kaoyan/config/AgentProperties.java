package com.kaoyan.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;
import jakarta.annotation.PostConstruct;

@Data
@Component
@ConfigurationProperties(prefix = "kaoyan.agent")
public class AgentProperties {
    private String baseUrl = "http://127.0.0.1:8001";
    private String internalKey = "";
    private int dailyTaskLimit = 30;
    private int minuteTaskLimit = 6;

    @PostConstruct
    public void validate() {
        if (dailyTaskLimit < 1 || minuteTaskLimit < 1) throw new IllegalStateException("任务限额需为正数");
        if (internalKey.length() < 16 || !internalKey.chars().allMatch(c -> c < 128))
            throw new IllegalStateException("AGENT_INTERNAL_KEY 必须显式配置，至少16位ASCII字符");
    }
}
