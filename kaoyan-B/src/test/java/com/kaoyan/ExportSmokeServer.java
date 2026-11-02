package com.kaoyan;

import com.kaoyan.service.PersonalDocumentService;
import com.kaoyan.learning.LearningContracts.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/** Synthetic export fixtures only; refuses anything other than this named in-memory H2 database. */
public class ExportSmokeServer {
    public static void main(String[] args) { new SpringApplication(KaoyanApplication.class, Fixtures.class).run(args); }
    @TestConfiguration(proxyBeanMethods = false)
    static class Fixtures {
        @Bean ApplicationRunner exportFixtures(JdbcTemplate db, PasswordEncoder passwords, PersonalDocumentService notes, ObjectMapper json) {
            return args -> {
                try (var connection = db.getDataSource().getConnection()) {
                    if (!connection.getMetaData().getURL().startsWith("jdbc:h2:mem:export-smoke"))
                        throw new IllegalStateException("导出夹具仅支持独立内存H2");
                }
                for (String name : List.of("export_student_1", "export_student_2"))
                    db.update("INSERT INTO `user`(username,password_hash,role,status,exam_year) VALUES(?,?,'STUDENT',1,2027)", name, passwords.encode("test-only-export-password"));
                long owner = db.queryForObject("SELECT id FROM `user` WHERE username='export_student_1'", Long.class);
                var note = notes.save(owner, null, new PersonalDocumentService.Save("排序复习笔记", "## 第一版\n\n归并排序保持相等元素相对次序。", null), null);
                notes.save(owner, note.get("id").toString(), new PersonalDocumentService.Save("排序复习笔记", "## 第二版\n\n独立完成例题，保留样本不足提示。\n\n| 知识点 | 样本 |\n| --- | --- |\n| 排序 | 8 |", 1), null);
                var group = new Group("test-point", "数据结构", "排序", "MEDIUM", 8, 3, 2, 1, 0.4, "SUFFICIENT", 0.1, 0.06, false);
                var sparse = new Group("sparse-point", "操作系统", "进程线程", "EASY", 2, 1, 0, 1, 0.5, "INSUFFICIENT", 0, null, false);
                var profile = new Profile(3, "learning-v1", "synthetic-v1", null, 0.1, 10, 2, 2, false, "ACTIVE", LocalDateTime.now().toString(), List.of(group, sparse), List.of("合成画像：样本不足，不代表录取概率。"));
                db.update("INSERT INTO learning_profile(user_id,revision,data_json,updated_at) VALUES(?,3,?,CURRENT_TIMESTAMP)", owner, json.writeValueAsString(profile));
                for (int i = 0; i < 10; i++) db.update("INSERT INTO practice_record(user_id,session_id,question_id,order_index,user_answer,is_correct,grading_status,question_snapshot,answered_at) VALUES(?,'test-session',?,?, 'B',?,'valid',?,CURRENT_TIMESTAMP)",
                        owner, i + 1, i, i < 4 ? 1 : 0, json.writeValueAsString(Map.of("subject", "数据结构", "knowledgePoint", "排序")));
                var result = Map.of("outcome", "COMPLETED", "resolvedTaskType", "CHAT", "explanationMode", "rules",
                        "answer", "## 学情分析\n\n本次有10条独立证据，排序应优先补强；这是合成测试结果。",
                        "studyPlan", Map.of("basis", List.of("合成画像 v3"), "days", List.of(Map.of("day", 1, "topic", "排序基础", "tasks", List.of("复习稳定性", "完成两道独立练习")))),
                        "documentProposal", Map.of("operation", "create", "title", "排序补强笔记", "content", "## 待确认笔记\n\n先理解，再练习。"),
                        "references", List.of(), "releaseId", "rag-v1-0123456789abcdef");
                db.update("INSERT INTO task(id,user_id,task_type,status,input_payload,result_payload,release_id,created_at,updated_at) VALUES('export-task',?,'CHAT','SUCCESS',?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
                        owner, "{\"private\":\"MUST_NOT_EXPORT_INPUT\"}", json.writeValueAsString(result), "rag-v1-0123456789abcdef");
            };
        }
    }
}
