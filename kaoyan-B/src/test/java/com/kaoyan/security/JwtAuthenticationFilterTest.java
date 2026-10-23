package com.kaoyan.security;

import com.kaoyan.entity.User;
import com.kaoyan.mapper.UserMapper;
import io.jsonwebtoken.Jwts;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class JwtAuthenticationFilterTest {
    @AfterEach void clearContext() { SecurityContextHolder.clearContext(); }

    @Test void roleIsReadFromCurrentAccountInsteadOfOldTokenClaim() throws Exception {
        var jwt = mock(JwtService.class);
        var users = mock(UserMapper.class);
        when(jwt.parse("test-token")).thenReturn(Jwts.claims().subject("1").id("jti").expiration(new java.util.Date(System.currentTimeMillis()+60000))
                .add("type", "access").add("role", "STUDENT").build());
        var user = new User(); user.setId(1L); user.setUsername("test"); user.setStatus(1); user.setRole("ADMIN");
        when(users.selectById(1L)).thenReturn(user);
        var request = new MockHttpServletRequest("GET", "/api/tasks");
        request.addHeader("Authorization", "Bearer test-token");
        new JwtAuthenticationFilter(jwt, users).doFilter(request, new MockHttpServletResponse(), (req, res) -> {
            var authentication = SecurityContextHolder.getContext().getAuthentication();
            assertNotNull(authentication);
            assertEquals("ADMIN", ((AuthUser) authentication.getPrincipal()).role());
            assertTrue(authentication.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN")));
        });
    }

    @Test void disabledAccountCannotAuthenticateWithStillValidToken() throws Exception {
        var jwt = mock(JwtService.class);
        var users = mock(UserMapper.class);
        when(jwt.parse("test-token")).thenReturn(Jwts.claims().subject("1").id("jti").expiration(new java.util.Date(System.currentTimeMillis()+60000)).add("type", "access").build());
        var user = new User(); user.setId(1L); user.setStatus(0);
        when(users.selectById(1L)).thenReturn(user);
        var request = new MockHttpServletRequest("GET", "/api/tasks");
        request.addHeader("Authorization", "Bearer test-token");
        new JwtAuthenticationFilter(jwt, users).doFilter(request, new MockHttpServletResponse(), (req, res) ->
                assertNull(SecurityContextHolder.getContext().getAuthentication()));
    }
}
