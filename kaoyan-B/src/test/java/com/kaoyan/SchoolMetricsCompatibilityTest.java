package com.kaoyan;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.entity.SchoolDetail;
import com.kaoyan.service.SchoolAdmissionMetrics;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowCallbackHandler;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class SchoolMetricsCompatibilityTest {
    private SchoolDetail detail() {
        SchoolDetail row = new SchoolDetail(); row.setId(1L); row.setEnrollmentCount(40);
        return row;
    }

    @Test void missingV14RetainsLegacyValuesWithoutCreatingTables() {
        var jdbc = new JdbcTemplate(new DriverManagerDataSource("jdbc:h2:mem:no-school-v14", "sa", ""));
        var row = detail();
        assertTrue(new SchoolAdmissionMetrics(jdbc, new ObjectMapper()).enrich(List.of(row)).isEmpty());
        assertEquals(40, row.getEnrollmentCount());
        assertNull(row.getAdmissionMetrics());
    }

    @Test void connectionFailureCannotBecomeAnEmptyCatalog() {
        var jdbc = mock(JdbcTemplate.class);
        doThrow(new DataAccessResourceFailureException("synthetic unavailable database")).when(jdbc)
                .query(anyString(), any(RowCallbackHandler.class), any(Object[].class));
        assertThrows(DataAccessResourceFailureException.class,
                () -> new SchoolAdmissionMetrics(jdbc, new ObjectMapper()).enrich(List.of(detail())));
    }
}
