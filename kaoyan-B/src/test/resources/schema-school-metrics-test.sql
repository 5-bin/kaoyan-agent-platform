CREATE TABLE school_admission_metric (
 school_detail_id BIGINT NOT NULL, metric_type VARCHAR(24) NOT NULL,
 metric_year INT, metric_value INT, status VARCHAR(24) NOT NULL,
 scope_key VARCHAR(64) NOT NULL, scope_label VARCHAR(500) NOT NULL, basis VARCHAR(40) NOT NULL,
 context_json VARCHAR(4000) NOT NULL, sources_json VARCHAR(20000) NOT NULL, notice VARCHAR(2000) NOT NULL,
 content_sha256 VARCHAR(64) NOT NULL, imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (school_detail_id, metric_type),
 FOREIGN KEY (school_detail_id) REFERENCES school_detail(id) ON DELETE CASCADE
);
