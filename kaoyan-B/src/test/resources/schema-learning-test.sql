-- H2 compatibility copy of V13; JSON uses LONGTEXT like the existing test fixtures.
-- Apply ONCE after V12, with backup and explicit database authorization.
-- Additive only. Legacy attempts deliberately have no session-item independence metadata.
CREATE TABLE practice_session (
 id VARCHAR(64) PRIMARY KEY, user_id BIGINT NOT NULL, kind VARCHAR(20) NOT NULL,
 state VARCHAR(20) NOT NULL, revision INT NOT NULL DEFAULT 0, current_index INT NOT NULL DEFAULT 0,
 blueprint_json LONGTEXT NOT NULL, created_at DATETIME NOT NULL, finished_at DATETIME NULL,
 INDEX ix_session_owner (user_id, created_at)
);
CREATE TABLE practice_session_item (
 record_id BIGINT PRIMARY KEY, session_id VARCHAR(64) NOT NULL,
 hint_level INT NOT NULL DEFAULT 0, draft_answer VARCHAR(10) NULL, submitted_at DATETIME NULL,
 INDEX ix_item_session (session_id)
);
CREATE TABLE practice_request (
 user_id BIGINT NOT NULL, request_id VARCHAR(64) NOT NULL, fingerprint VARCHAR(64) NOT NULL,
 response_json LONGTEXT NOT NULL, created_at DATETIME NOT NULL,
 PRIMARY KEY (user_id, request_id)
);
CREATE TABLE question_version (
 question_id BIGINT NOT NULL, version INT NOT NULL, snapshot_json LONGTEXT NOT NULL,
 withdrawn INT NOT NULL DEFAULT 0, withdrawal_reason VARCHAR(2000) NULL,
 created_at DATETIME NOT NULL, PRIMARY KEY (question_id, version)
);
CREATE TABLE learning_blueprint (
 id VARCHAR(64) PRIMARY KEY, version INT NOT NULL, config_json LONGTEXT NOT NULL,
 reviewer_id BIGINT NOT NULL, created_at DATETIME(6) NOT NULL
);
CREATE TABLE learning_profile (
 user_id BIGINT PRIMARY KEY, revision INT NOT NULL DEFAULT 0, data_json LONGTEXT NOT NULL,
 updated_at DATETIME NOT NULL
);
CREATE TABLE learning_profile_history (
 user_id BIGINT NOT NULL, revision INT NOT NULL, data_json LONGTEXT NOT NULL,
 created_at DATETIME NOT NULL, PRIMARY KEY (user_id, revision)
);
CREATE TABLE learning_event (
 id VARCHAR(64) PRIMARY KEY, user_id BIGINT NOT NULL, event_key VARCHAR(150) NOT NULL UNIQUE,
 state VARCHAR(20) NOT NULL, attempts INT NOT NULL DEFAULT 0,
 next_at DATETIME NOT NULL, lease_until DATETIME NULL, created_at DATETIME NOT NULL,
 INDEX ix_event_due (state, next_at)
);
CREATE TABLE learning_recommendation_settings (
 user_id BIGINT PRIMARY KEY, revision INT NOT NULL DEFAULT 0, enabled INT NOT NULL DEFAULT 0,
 preferences_json LONGTEXT NOT NULL, pending_reason VARCHAR(40) NULL, not_before DATETIME NULL,
 last_task_id VARCHAR(64) NULL, last_profile_revision INT NULL, last_score DOUBLE NULL,
 last_sufficient INT NOT NULL DEFAULT 0, last_completed_at DATETIME NULL,
 last_release_id VARCHAR(64) NULL, last_profile_hash VARCHAR(64) NULL,
 run_token VARCHAR(64) NULL, run_until DATETIME NULL, pending_task_id VARCHAR(64) NULL, attempts INT NOT NULL DEFAULT 0
);
CREATE TABLE school_historical_metric (
 id VARCHAR(64) PRIMARY KEY, program_id VARCHAR(100) NOT NULL, school VARCHAR(255) NOT NULL,
 college VARCHAR(255) NOT NULL, major_code VARCHAR(6) NOT NULL, metric_year INT NOT NULL,
 metric_type VARCHAR(40) NOT NULL, exam_subject VARCHAR(3) NULL,
 max_score INT NOT NULL, score DOUBLE NOT NULL, source_json LONGTEXT NOT NULL,
 reviewer_id BIGINT NOT NULL, created_at DATETIME NOT NULL
);
