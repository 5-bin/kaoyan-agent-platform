package com.kaoyan;

import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;

/** Loopback browser smoke fixtures; never packaged in the production JAR. */
public class QuestionAdminSmokeServer {
    public static void main(String[] args) {
        new SpringApplication(KaoyanApplication.class, FrameworkSmokeServer.SmokeConfig.class, Fixtures.class).run(args);
    }

    @TestConfiguration(proxyBeanMethods = false)
    static class Fixtures {
        @Bean ApplicationRunner questionAccounts(JdbcTemplate jdbc, PasswordEncoder passwords) {
            return args -> {
                try (var connection = jdbc.getDataSource().getConnection()) {
                    if (!connection.getMetaData().getURL().startsWith("jdbc:h2:mem:question-admin-smoke"))
                        throw new IllegalStateException("Question browser fixtures require the isolated in-memory H2 database");
                }
                for (String username : new String[]{"question_admin", "question_reviewer", "question_student"}) {
                    jdbc.update("INSERT INTO `user`(username,password_hash,role,status) VALUES(?,?,?,1)", username,
                        passwords.encode("test-only-question-password"), username.endsWith("student") ? "STUDENT" : "ADMIN");
                }
            };
        }
    }
}
