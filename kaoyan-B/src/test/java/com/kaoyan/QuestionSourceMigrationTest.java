package com.kaoyan;

import org.h2.jdbcx.JdbcDataSource;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import static org.junit.jupiter.api.Assertions.*;

class QuestionSourceMigrationTest {
    @Test void additiveSourceMigrationPreservesQuestionsAndSnapshotsWithUnknownProvenance() {
        var ds = new JdbcDataSource();
        ds.setURL("jdbc:h2:mem:source-migration;MODE=MySQL;DB_CLOSE_DELAY=-1");
        var jdbc = new JdbcTemplate(ds);
        jdbc.execute("CREATE TABLE question(id BIGINT PRIMARY KEY,content VARCHAR(255),version INT,review_status VARCHAR(30))");
        jdbc.execute("CREATE TABLE practice_record(id BIGINT PRIMARY KEY,question_id BIGINT,question_snapshot VARCHAR(1000))");
        jdbc.update("INSERT INTO question VALUES(1,'保留的旧题',2,'APPROVED')");
        jdbc.update("INSERT INTO practice_record VALUES(1,1,'original-snapshot')");
        new ResourceDatabasePopulator(new ClassPathResource("db/V9__question_source.sql")).execute(ds);
        assertEquals("保留的旧题", jdbc.queryForObject("SELECT content FROM question WHERE id=1", String.class));
        assertEquals("APPROVED", jdbc.queryForObject("SELECT review_status FROM question WHERE id=1", String.class));
        assertEquals(2, jdbc.queryForObject("SELECT version FROM question WHERE id=1", Integer.class));
        assertEquals("original-snapshot", jdbc.queryForObject("SELECT question_snapshot FROM practice_record WHERE id=1", String.class));
        for (String field : new String[]{"source_type", "source_name", "source_locator", "source_year", "source_question_no", "permission_note"})
            assertNull(jdbc.queryForObject("SELECT " + field + " FROM question WHERE id=1", Object.class));
        jdbc.update("UPDATE question SET source_type='ORIGINAL',source_name='新登记',source_locator='记录1',source_year=2026,source_question_no='1',permission_note='自编' WHERE id=1");
        assertEquals("新登记", jdbc.queryForObject("SELECT source_name FROM question WHERE id=1", String.class));
    }
}
