package com.kaoyan.security;

import com.kaoyan.common.ApiException;
import com.kaoyan.config.JwtProperties;
import com.kaoyan.entity.User;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import lombok.RequiredArgsConstructor;
// import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * JWT 签发 / 解析 / 黑名单
 */
@Service
@RequiredArgsConstructor
public class JwtService {

    /** Redis 黑名单 key 前缀 */
    private static final String BLACKLIST_PREFIX = "jwt:blacklist:";

    private final JwtProperties props;
    // private final StringRedisTemplate redis;  // 暂时不用 Redis

    private SecretKey key() {
        return Keys.hmacShaKeyFor(props.getSecret().getBytes(StandardCharsets.UTF_8));
    }

    /**
     * 签发 access token
     *
     * @param user 用户
     * @return token
     */
    public String generateAccess(User user) {
        return build(user, "access", props.getAccessExpireMinutes() * 60);
    }

    /**
     * 签发 refresh token
     *
     * @param user 用户
     * @return token
     */
    public String generateRefresh(User user) {
        return build(user, "refresh", props.getRefreshExpireDays() * 24 * 60 * 60);
    }

    private String build(User user, String type, long ttlSeconds) {
        Date now = new Date();
        Date exp = new Date(now.getTime() + ttlSeconds * 1000);
        return Jwts.builder()
                .subject(String.valueOf(user.getId()))
                .claim("username", user.getUsername())
                .claim("role", user.getRole())
                .claim("type", type)
                .id(UUID.randomUUID().toString())
                .issuer(props.getIssuer())
                .issuedAt(now)
                .expiration(exp)
                .signWith(key())
                .compact();
    }

    /**
     * 校验签名与过期，失败抛 401
     *
     * @param token token
     * @return Claims
     */
    public Claims parse(String token) {
        try {
            return Jwts.parser().verifyWith(key()).build()
                    .parseSignedClaims(token).getPayload();
        } catch (Exception e) {
            throw new ApiException(401, 401, "登录已失效，请重新登录");
        }
    }

    /**
     * 将 jti 写入 Redis 黑名单
     *
     * @param jti        token ID
     * @param ttlSeconds 剩余有效期（秒）
     */
    public void revoke(String jti, long ttlSeconds) {
        // Redis 黑名单暂时关闭：直接 no-op
        // if (jti == null || ttlSeconds <= 0) return;
        // redis.opsForValue().set(BLACKLIST_PREFIX + jti, "1", ttlSeconds, TimeUnit.SECONDS);
    }

    /**
     * 判断 jti 是否已被吊销
     *
     * @param jti token ID
     * @return true 表示已吊销
     */
    public boolean isRevoked(String jti) {
        // Redis 黑名单暂时关闭：一律按未吊销处理
        return false;
    }
}
