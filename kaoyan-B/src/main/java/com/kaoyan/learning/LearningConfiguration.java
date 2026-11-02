package com.kaoyan.learning;

import org.springframework.context.annotation.Configuration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.EnableScheduling;

@Configuration
@EnableScheduling
@ConditionalOnProperty(name="kaoyan.learning.enabled", havingValue="true")
public class LearningConfiguration {
    @org.springframework.context.annotation.Bean(name="taskScheduler")
    org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler learningScheduler() {
        var scheduler=new org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler();
        scheduler.setPoolSize(2);scheduler.setThreadNamePrefix("learning-worker-");return scheduler;
    }
    @org.springframework.context.annotation.Bean
    org.springframework.boot.ApplicationRunner learningSchemaCheck(org.springframework.jdbc.core.JdbcTemplate jdbc) {
        return args -> {
            try {
                for(String table:java.util.List.of("practice_session","practice_session_item","practice_request","question_version",
                    "learning_blueprint","learning_profile","learning_profile_history","learning_event","learning_recommendation_settings","school_historical_metric"))
                    jdbc.queryForObject("SELECT COUNT(*) FROM "+table+" WHERE 1=0",Integer.class);
            } catch(Exception ignored) { throw new IllegalStateException("LEARNING_V13_MIGRATION_REQUIRED"); }
        };
    }
}
