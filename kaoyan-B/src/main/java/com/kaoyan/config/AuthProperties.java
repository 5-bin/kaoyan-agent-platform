package com.kaoyan.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/** Server-owned registration policy; existing environments remain open by default. */
@Data
@Component
@ConfigurationProperties(prefix = "kaoyan.auth")
public class AuthProperties {
    private boolean registrationEnabled = true;
}
