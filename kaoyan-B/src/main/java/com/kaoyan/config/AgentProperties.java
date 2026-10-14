package com.kaoyan.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "kaoyan.agent")
public class AgentProperties {
    private String baseUrl = "http://127.0.0.1:8001";
    private String internalKey = "kaoyan-agent-internal-key-2026";
}
