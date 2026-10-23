-- Additive only. Apply once after V11; do not rerun V1 on an existing database.
CREATE TABLE assistant_privacy (
 user_id BIGINT PRIMARY KEY, model_allowed BOOLEAN NOT NULL DEFAULT FALSE,
 scopes_json LONGTEXT NOT NULL, provider VARCHAR(500) NOT NULL,
 version INT NOT NULL DEFAULT 1, consented_at TIMESTAMP NULL,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE assistant_action (
 id VARCHAR(36) PRIMARY KEY, user_id BIGINT NOT NULL, conversation_id VARCHAR(36) NOT NULL,
 task_id VARCHAR(36) NOT NULL UNIQUE, operation VARCHAR(32) NOT NULL, status VARCHAR(20) NOT NULL,
 payload_json LONGTEXT NOT NULL, result_json LONGTEXT NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_assistant_action_owner (user_id, created_at)
);
