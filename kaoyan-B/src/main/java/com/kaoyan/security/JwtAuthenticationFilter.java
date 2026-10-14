package com.kaoyan.security;

import com.kaoyan.common.ApiException;
import io.jsonwebtoken.Claims;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

/**
 * JWT 认证过滤器：解析 Bearer Token，写入 SecurityContext
 */
@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtService jwtService;
    private final com.kaoyan.mapper.UserMapper userMapper;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String header = request.getHeader("Authorization");
        if (header == null || !header.startsWith("Bearer ")) {
            chain.doFilter(request, response);
            return;
        }
        String token = header.substring(7);
        try {
            Claims claims = jwtService.parse(token);
            // refresh token 不能当 access 用
            if (!"access".equals(claims.get("type", String.class))) {
                chain.doFilter(request, response);
                return;
            }
            // 黑名单校验
            if (jwtService.isRevoked(claims.getId())) {
                chain.doFilter(request, response);
                return;
            }
            Long userId = Long.valueOf(claims.getSubject());
            var user = userMapper.selectById(userId);
            if (user == null || !Integer.valueOf(1).equals(user.getStatus())) {
                SecurityContextHolder.clearContext();
                chain.doFilter(request, response);
                return;
            }
            String username = user.getUsername();
            String role = user.getRole();
            AuthUser principal = new AuthUser(userId, username, role);
            UsernamePasswordAuthenticationToken auth = new UsernamePasswordAuthenticationToken(
                    principal, null,
                    List.of(new SimpleGrantedAuthority("ROLE_" + role)));
            SecurityContextHolder.getContext().setAuthentication(auth);
        } catch (ApiException | IllegalArgumentException e) {
            SecurityContextHolder.clearContext();
        }
        chain.doFilter(request, response);
    }
}
