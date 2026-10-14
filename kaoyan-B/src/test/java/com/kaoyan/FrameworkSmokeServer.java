package com.kaoyan;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

/** 仅供scripts/smoke-current.py启动；H2与Redis替身不打进生产JAR。 */
public class FrameworkSmokeServer {
    public static void main(String[] args) {
        SpringApplication app = new SpringApplication(KaoyanApplication.class, SmokeConfig.class);
        app.run(args);
    }

    @TestConfiguration(proxyBeanMethods = false)
    static class SmokeConfig {
        @Bean StringRedisTemplate smokeRedis() {
            var expiry = new ConcurrentHashMap<String, Long>();
            var redis = mock(StringRedisTemplate.class);
            ValueOperations<String, String> values = mock(ValueOperations.class);
            when(redis.opsForValue()).thenReturn(values);
            doAnswer(call -> {
                String key = call.getArgument(0);
                long ttl = call.getArgument(2);
                TimeUnit unit = call.getArgument(3);
                expiry.put(key, System.currentTimeMillis() + unit.toMillis(ttl));
                return null;
            }).when(values).set(anyString(), anyString(), anyLong(), any(TimeUnit.class));
            when(redis.hasKey(anyString())).thenAnswer(call ->
                expiry.getOrDefault(call.getArgument(0), 0L) > System.currentTimeMillis());
            return redis;
        }
    }
}
