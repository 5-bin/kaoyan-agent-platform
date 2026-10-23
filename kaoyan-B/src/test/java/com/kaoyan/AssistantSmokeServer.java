package com.kaoyan;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.jdbc.core.JdbcTemplate;
import javax.sql.DataSource;

/** Test-classpath-only synthetic fixtures. Refuses daily databases and network H2. */
public class AssistantSmokeServer {
    public static void main(String[] args) {
        new SpringApplication(KaoyanApplication.class,FrameworkSmokeServer.SmokeConfig.class,Fixtures.class).run(args);
    }
    @TestConfiguration(proxyBeanMethods=false)
    static class Fixtures {
        @Bean ApplicationRunner assistantFixtures(JdbcTemplate jdbc,DataSource data) {
            return args -> {
                try(var connection=data.getConnection()) {
                    String url=connection.getMetaData().getURL();
                    if(!url.startsWith("jdbc:h2:file:") || !url.contains("kaoyan-chat-chain-")) throw new IllegalStateException("测试夹具拒绝非隔离数据库");
                }
                if(jdbc.queryForObject("SELECT COUNT(*) FROM question WHERE id=9011",Integer.class)==0)
                    jdbc.update("INSERT INTO question(id,subject,knowledge_point,content,option_a,option_b,option_c,option_d,answer,analysis,difficulty,question_type,version,active,stable_order,review_status) VALUES(9011,'操作系统','线程','合成测试：同进程的线程共享什么？','各自的栈','地址空间','各自的寄存器','独立的程序计数器','B','合成解析：同进程线程共享地址空间，保留独立执行状态。','EASY','SINGLE_CHOICE',1,1,1,'APPROVED')");
                jdbc.execute("CREATE TABLE IF NOT EXISTS document(id BIGINT PRIMARY KEY,title VARCHAR(255),subject VARCHAR(50),content TEXT,source_url VARCHAR(1000),status VARCHAR(30),creator_user_id BIGINT,reviewer_user_id BIGINT,reviewed_at TIMESTAMP,created_at TIMESTAMP,updated_at TIMESTAMP)");
                if(jdbc.queryForObject("SELECT COUNT(*) FROM document WHERE id=9122",Integer.class)==0)
                    jdbc.update("INSERT INTO document(id,title,subject,content,status,created_at,updated_at) VALUES(9122,'合成线程复习资料','操作系统','合成学习资料正文：同一进程的线程共享地址空间，各线程保留各自的栈和寄存器。仅供隔离测试，不是正式教材。','PUBLISHED',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)");
            };
        }
    }
}
