package com.kaoyan;

import org.h2.jdbcx.JdbcDataSource;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import static org.junit.jupiter.api.Assertions.*;

class TaskSoftDeleteMigrationTest {
    @Test void additiveMigrationPreservesExistingTaskAndDefaultsToVisible() {
        var dataSource = new JdbcDataSource();
        dataSource.setURL("jdbc:h2:mem:soft-delete-migration;MODE=MySQL;DB_CLOSE_DELAY=-1");
        var jdbc = new JdbcTemplate(dataSource);
        jdbc.execute("CREATE TABLE task(id VARCHAR(36) PRIMARY KEY, result_payload VARCHAR(1000))");
        jdbc.update("INSERT INTO task(id,result_payload) VALUES('existing','historical-result')");
        new ResourceDatabasePopulator(new ClassPathResource("db/V8__task_soft_delete.sql")).execute(dataSource);
        assertEquals("historical-result", jdbc.queryForObject("SELECT result_payload FROM task WHERE id='existing'", String.class));
        assertNull(jdbc.queryForObject("SELECT deleted_at FROM task WHERE id='existing'", java.sql.Timestamp.class));
        jdbc.update("INSERT INTO task(id) VALUES('new')");
        assertEquals(2, jdbc.queryForObject("SELECT COUNT(*) FROM task WHERE deleted_at IS NULL", Integer.class));
    }
}
