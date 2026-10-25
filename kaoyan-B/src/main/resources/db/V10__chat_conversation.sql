-- Incremental migration. Apply once to an existing V9 database; never rerun V1.
CREATE TABLE chat_conversation (
 id VARCHAR(36) PRIMARY KEY, user_id BIGINT NOT NULL, title VARCHAR(100) NOT NULL,
 conditions_json LONGTEXT NOT NULL, profile_json LONGTEXT NOT NULL, next_sequence INT NOT NULL DEFAULT 1,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_conversation_owner (user_id, updated_at)
);
CREATE TABLE chat_message (
 id VARCHAR(36) PRIMARY KEY, conversation_id VARCHAR(36) NOT NULL, user_id BIGINT NOT NULL,
 sequence_no INT NOT NULL, content TEXT NOT NULL, document_id VARCHAR(36),
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_message_sequence (conversation_id, sequence_no)
);
CREATE TABLE chat_generation (
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
