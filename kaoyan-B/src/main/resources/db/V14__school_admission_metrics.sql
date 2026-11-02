-- Apply ONCE after backup, restore verification and isolated rehearsal.
-- No startup auto-migration; no changes to old school_detail scores or RAG metrics.
CREATE TABLE school_admission_metric (
 school_detail_id BIGINT UNSIGNED NOT NULL,
 metric_type VARCHAR(24) NOT NULL,
 metric_year INT NULL,
 metric_value INT NULL,
 status VARCHAR(24) NOT NULL,
 scope_key VARCHAR(64) NOT NULL,
 scope_label VARCHAR(500) NOT NULL,
 basis VARCHAR(40) NOT NULL,
 context_json JSON NOT NULL,
 sources_json JSON NOT NULL,
 notice VARCHAR(2000) NOT NULL,
 content_sha256 CHAR(64) NOT NULL,
 imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (school_detail_id, metric_type),
 CONSTRAINT fk_admission_detail FOREIGN KEY (school_detail_id) REFERENCES school_detail(id) ON DELETE CASCADE,
 CONSTRAINT ck_admission_type CHECK (metric_type IN ('ENROLLMENT','CUTOFF_REFERENCE')),
 CONSTRAINT ck_admission_status CHECK (status IN ('OFFICIAL','UNVERIFIED','NOT_PUBLISHED','NOT_FOUND','SCOPE_MISMATCH','CONFLICT')),
 CONSTRAINT ck_admission_value CHECK (
   (status IN ('OFFICIAL','UNVERIFIED') AND metric_value IS NOT NULL AND metric_value >= 0 AND metric_year IS NOT NULL)
   OR (status NOT IN ('OFFICIAL','UNVERIFIED') AND metric_value IS NULL)
 )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
