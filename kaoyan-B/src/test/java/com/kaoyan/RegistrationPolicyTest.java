package com.kaoyan;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.config.AuthProperties;
import com.kaoyan.service.UserService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.jdbc.core.JdbcTemplate;
import java.util.Map;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.url=jdbc:h2:mem:registration_policy;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER",
    "spring.datasource.username=sa", "spring.datasource.password=",
    "spring.sql.init.mode=always", "spring.sql.init.schema-locations=classpath:schema-test.sql",
    "jwt.secret=test-only-jwt-key-at-least-32-characters",
    "kaoyan.agent.internal-key=test-only-internal-key-12345"
})
@AutoConfigureMockMvc
class RegistrationPolicyTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired AuthProperties policy;
    @Autowired UserService users;
    @Autowired JdbcTemplate jdbc;
    @MockitoBean StringRedisTemplate redis;

    @Test void registrationDefaultsOpenAndReturnsOnlyPublicFields() throws Exception {
        assertTrue(policy.isRegistrationEnabled());
        String body=json.writeValueAsString(Map.of("username", "rp_"+UUID.randomUUID().toString().substring(0,8), "password", "synthetic-pass"));
        var response=mvc.perform(post("/api/auth/register").contentType("application/json").content(body))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        var data=json.readTree(response).path("data");
        assertEquals("STUDENT",data.path("role").asText());
        assertFalse(data.has("passwordHash"));assertFalse(data.has("password"));
        assertEquals(12,data.size());
        var config=json.readTree(mvc.perform(get("/api/auth/config")).andExpect(status().isOk()).andReturn().getResponse().getContentAsString()).path("data");
        assertEquals(1,config.size());assertTrue(config.path("registrationEnabled").asBoolean());
    }

    @Test void closedRegistrationRejectsDirectServiceAndHttpButExistingLoginWorks() throws Exception {
        String name="closed_"+UUID.randomUUID().toString().substring(0,8);
        users.register(name,"synthetic-pass");
        long count=jdbc.queryForObject("SELECT COUNT(*) FROM `user`",Long.class);
        policy.setRegistrationEnabled(false);
        try {
            var response=mvc.perform(post("/api/auth/register").contentType("application/json")
                .content(json.writeValueAsString(Map.of("username",name+"new","password","synthetic-pass"))))
                .andExpect(status().isForbidden()).andReturn().getResponse().getContentAsString();
            assertEquals("当前暂不开放注册",json.readTree(response).path("message").asText());
            var error=assertThrows(com.kaoyan.common.ApiException.class,()->users.register(name+"direct","synthetic-pass"));
            assertEquals(403,error.getHttpStatus());
            assertEquals(count,jdbc.queryForObject("SELECT COUNT(*) FROM `user`",Long.class));
            mvc.perform(get("/api/auth/config")).andExpect(status().isOk()).andExpect(jsonPath("$.data.registrationEnabled").value(false));
            mvc.perform(post("/api/auth/login").contentType("application/json")
                .content(json.writeValueAsString(Map.of("username",name,"password","synthetic-pass"))))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.accessToken").isString());
        } finally { policy.setRegistrationEnabled(true); }
    }
}
