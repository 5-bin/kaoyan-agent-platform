package com.kaoyan.security;

import com.kaoyan.config.JwtProperties;
import com.kaoyan.config.OssProperties;
import com.kaoyan.util.OssUtil;
import com.kaoyan.common.ApiException;
import com.kaoyan.entity.User;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import java.util.concurrent.TimeUnit;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class JwtServiceTest {
    @Test void signedTokensHaveBoundedLifetimeAndIssuer() {
        var props = new JwtProperties(); props.setSecret("test-only-signing-key-at-least-32-characters");
        var service = new JwtService(props, mock(StringRedisTemplate.class));
        var user = new User(); user.setId(1L); user.setUsername("test"); user.setRole("STUDENT");
        String token = service.generateAccess(user);
        String header = new String(java.util.Base64.getUrlDecoder().decode(token.split("\\.")[0]), java.nio.charset.StandardCharsets.UTF_8);
        assertTrue(header.contains("\"alg\":\"HS256\""));
        var claims = service.parse(token);
        assertEquals("access", claims.get("type"));
        assertEquals(3600000, claims.getExpiration().getTime() - claims.getIssuedAt().getTime());
        props.setIssuer("another-issuer");
        assertThrows(ApiException.class, () -> service.parse(token));
    }

    @Test void logoutWritesExpiringBlacklistAndChecksIt() {
        var redis = mock(StringRedisTemplate.class);
        ValueOperations<String,String> values = mock(ValueOperations.class);
        when(redis.opsForValue()).thenReturn(values);
        var service = new JwtService(new JwtProperties(), redis);
        service.revoke("test-jti", 60);
        verify(values).set("jwt:blacklist:test-jti", "1", 60, TimeUnit.SECONDS);
        when(redis.hasKey("jwt:blacklist:test-jti")).thenReturn(true);
        assertTrue(service.isRevoked("test-jti"));
    }

    @Test void optionalOssDoesNotPreventStartupButFailsExplicitlyOnUse() {
        var oss = new OssUtil(new OssProperties());
        assertDoesNotThrow(oss::init);
        assertEquals(503, assertThrows(ApiException.class, () -> oss.upload(null, "avatar")).getHttpStatus());
    }

    @Test void invalidCredentialsFailWithoutIncludingTheirValuesInDiagnostics() {
        var jwt = new JwtProperties(); jwt.setSecret("short-test-credential");
        var exception = assertThrows(IllegalStateException.class, jwt::afterPropertiesSet);
        assertFalse(exception.getMessage().contains(jwt.getSecret()));
        assertFalse(jwt.toString().contains(jwt.getSecret()));
        var agent = new com.kaoyan.config.AgentProperties(); agent.setInternalKey("short-test-key");
        var failure = assertThrows(IllegalStateException.class, agent::afterPropertiesSet);
        assertFalse(failure.getMessage().contains(agent.getInternalKey()));
        assertFalse(agent.toString().contains(agent.getInternalKey()));
    }
}
