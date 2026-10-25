CREATE TABLE personal_document (
 id VARCHAR(36) PRIMARY KEY, user_id BIGINT NOT NULL, title VARCHAR(100) NOT NULL,
 content LONGTEXT NOT NULL, version INT NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_personal_document_owner (user_id, updated_at)
);
CREATE TABLE personal_document_version (
 document_id VARCHAR(36) NOT NULL, version INT NOT NULL, user_id BIGINT NOT NULL,
 title VARCHAR(100) NOT NULL, content LONGTEXT NOT NULL, source_task_id VARCHAR(36),
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (document_id, version), UNIQUE KEY uq_document_source_task (source_task_id)
);
