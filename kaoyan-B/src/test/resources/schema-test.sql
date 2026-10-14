CREATE TABLE IF NOT EXISTS `user` (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(64) UNIQUE NOT NULL,
 password_hash VARCHAR(255), role VARCHAR(32), avatar_url VARCHAR(500),
 target_school VARCHAR(100), target_major VARCHAR(100), exam_year INT,
 background VARCHAR(2000), status INT, created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS task (
 id VARCHAR(64) PRIMARY KEY, user_id BIGINT, task_type VARCHAR(40), status VARCHAR(20),
 input_payload VARCHAR(20000), result_payload VARCHAR(20000), release_id VARCHAR(64),
 error_message VARCHAR(1000), created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS practice_record (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, user_id BIGINT, session_id VARCHAR(64),
 question_id BIGINT, order_index INT, user_answer VARCHAR(10), is_correct INT,
 grading_status VARCHAR(20), question_snapshot VARCHAR(50000), answered_at TIMESTAMP, created_at TIMESTAMP
);
