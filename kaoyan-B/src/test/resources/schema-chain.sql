CREATE TABLE IF NOT EXISTS `user` (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(64) UNIQUE NOT NULL, password_hash VARCHAR(100),
 role VARCHAR(20), status INT, avatar_url VARCHAR(500), target_school VARCHAR(255), target_major VARCHAR(255),
 exam_year INT, background TEXT, created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS task (
 id VARCHAR(36) PRIMARY KEY, user_id BIGINT, task_type VARCHAR(50), status VARCHAR(20),
 input_payload VARCHAR(100000), result_payload VARCHAR(100000), release_id VARCHAR(64), error_message TEXT,
 created_at TIMESTAMP, updated_at TIMESTAMP, deleted_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS practice_record (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, user_id BIGINT, session_id VARCHAR(36), question_id BIGINT,
 order_index INT, user_answer VARCHAR(10), is_correct INT, grading_status VARCHAR(20), question_snapshot VARCHAR(50000),
 answered_at TIMESTAMP, created_at TIMESTAMP
);

-- Chat isolation schema: V10__chat_conversation.sql
-- Incremental migration. Apply once to an existing V9 database; never rerun V1.
CREATE TABLE IF NOT EXISTS chat_conversation (
 id VARCHAR(36) PRIMARY KEY, user_id BIGINT NOT NULL, title VARCHAR(100) NOT NULL,
 conditions_json LONGTEXT NOT NULL, profile_json LONGTEXT NOT NULL, next_sequence INT NOT NULL DEFAULT 1,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_conversation_owner (user_id, updated_at)
);
CREATE TABLE IF NOT EXISTS chat_message (
 id VARCHAR(36) PRIMARY KEY, conversation_id VARCHAR(36) NOT NULL, user_id BIGINT NOT NULL,
 sequence_no INT NOT NULL, content TEXT NOT NULL, document_id VARCHAR(36),
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_message_sequence (conversation_id, sequence_no)
);
CREATE TABLE IF NOT EXISTS chat_generation (
 task_id VARCHAR(36) PRIMARY KEY, conversation_id VARCHAR(36) NOT NULL, message_id VARCHAR(36) NOT NULL,
 user_id BIGINT NOT NULL, attempt_no INT NOT NULL, client_request_id VARCHAR(64) NOT NULL,
 request_hash VARCHAR(64) NOT NULL, status VARCHAR(20) NOT NULL,
 active_conversation_id VARCHAR(36), context_json LONGTEXT NOT NULL, draft_json LONGTEXT NOT NULL,
 result_json LONGTEXT, version BIGINT NOT NULL DEFAULT 0, stage VARCHAR(100), error_message VARCHAR(255),
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_generation_request (conversation_id, client_request_id),
 UNIQUE KEY uq_generation_active (active_conversation_id),
 UNIQUE KEY uq_generation_attempt (message_id, attempt_no),
 INDEX idx_generation_conversation (conversation_id, created_at)
);

-- Chat isolation schema: V11__personal_document.sql
CREATE TABLE IF NOT EXISTS personal_document (
 id VARCHAR(36) PRIMARY KEY, user_id BIGINT NOT NULL, title VARCHAR(100) NOT NULL,
 content LONGTEXT NOT NULL, version INT NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_personal_document_owner (user_id, updated_at)
);
CREATE TABLE IF NOT EXISTS personal_document_version (
 document_id VARCHAR(36) NOT NULL, version INT NOT NULL, user_id BIGINT NOT NULL,
 title VARCHAR(100) NOT NULL, content LONGTEXT NOT NULL, source_task_id VARCHAR(36),
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (document_id, version), UNIQUE KEY uq_document_source_task (source_task_id)
);

-- Assistant privacy isolation schema (V12)
-- Additive only. Apply once after V11; do not rerun V1 on an existing database.
CREATE TABLE IF NOT EXISTS assistant_privacy (
 user_id BIGINT PRIMARY KEY, model_allowed BOOLEAN NOT NULL DEFAULT FALSE,
 scopes_json LONGTEXT NOT NULL, provider VARCHAR(500) NOT NULL,
 version INT NOT NULL DEFAULT 1, consented_at TIMESTAMP NULL,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS assistant_action (
 id VARCHAR(36) PRIMARY KEY, user_id BIGINT NOT NULL, conversation_id VARCHAR(36) NOT NULL,
 task_id VARCHAR(36) NOT NULL UNIQUE, operation VARCHAR(32) NOT NULL, status VARCHAR(20) NOT NULL,
 payload_json LONGTEXT NOT NULL, result_json LONGTEXT NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_assistant_action_owner (user_id, created_at)
);
