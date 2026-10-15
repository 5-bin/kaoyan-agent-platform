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
