package course.kaoyan.auth;

import course.kaoyan.common.exception.ApiException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.util.List;
import java.util.Map;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.filter.OncePerRequestFilter;

@Configuration
public class SecurityConfig {
    @Bean PasswordEncoder passwordEncoder() { return new BCryptPasswordEncoder(); }
    @Bean SecurityFilterChain chain(HttpSecurity http, AuthService auth, ObjectMapper mapper) throws Exception {
        OncePerRequestFilter bearer = new OncePerRequestFilter() {
            @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain) throws ServletException, IOException {
                String header = request.getHeader("Authorization");
                if (header != null && header.startsWith("Bearer ")) {
                    try {
                        AuthService.User user = auth.authenticate(header.substring(7));
                        var authorities = List.of(new SimpleGrantedAuthority("ROLE_" + user.role().toUpperCase(java.util.Locale.ROOT)));
                        SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(user, null, authorities));
                    } catch (ApiException e) {
                        response.setStatus(401); response.setContentType("application/json;charset=UTF-8");
                        mapper.writeValue(response.getOutputStream(), Map.of("code", e.code, "message", e.getMessage())); return;
                    }
                }
                chain.doFilter(request, response);
            }
        };
        return http.csrf(c -> c.disable()).sessionManagement(c -> c.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(c -> c.requestMatchers("/api/auth/register", "/api/auth/login", "/api/health").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .requestMatchers("/api/**").authenticated().anyRequest().permitAll())
            .exceptionHandling(c -> c.authenticationEntryPoint((request, response, e) -> {
                response.setStatus(401); response.setContentType("application/json;charset=UTF-8");
                mapper.writeValue(response.getOutputStream(), Map.of("code", "UNAUTHORIZED", "message", "请先登录"));
            }).accessDeniedHandler((request, response, e) -> {
                response.setStatus(403); response.setContentType("application/json;charset=UTF-8");
                mapper.writeValue(response.getOutputStream(), Map.of("code", "FORBIDDEN", "message", "需要管理员权限"));
            }))
            .addFilterBefore(bearer, UsernamePasswordAuthenticationFilter.class).build();
    }
}

