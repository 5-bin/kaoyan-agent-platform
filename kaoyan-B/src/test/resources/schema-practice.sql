CREATE TABLE IF NOT EXISTS question (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, subject VARCHAR(50), knowledge_point VARCHAR(255), content TEXT,
 option_a TEXT, option_b TEXT, option_c TEXT, option_d TEXT, answer VARCHAR(10), analysis TEXT,
 difficulty VARCHAR(20), question_type VARCHAR(30), version INT, active INT, stable_order INT,
 review_status VARCHAR(30), reviewer_user_id BIGINT, reviewed_at TIMESTAMP, review_comment TEXT,
 source_type VARCHAR(20), source_name VARCHAR(255), source_locator VARCHAR(1000), source_year INT,
 source_question_no VARCHAR(64), permission_note VARCHAR(2000),
 created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_question_mark (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, user_id BIGINT, question_id BIGINT, is_favorite INT,
 is_wrong INT, wrong_count INT, last_wrong_at TIMESTAMP, created_at TIMESTAMP, updated_at TIMESTAMP,
 UNIQUE(user_id, question_id)
);
CREATE TABLE IF NOT EXISTS study_stat (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, user_id BIGINT, stat_date DATE, question_count INT,
 correct_count INT, study_minutes INT, created_at TIMESTAMP, updated_at TIMESTAMP,
 UNIQUE(user_id, stat_date)
);
CREATE TABLE IF NOT EXISTS document (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, title VARCHAR(255), subject VARCHAR(50), content TEXT,
 source_url VARCHAR(1000), status VARCHAR(30), creator_user_id BIGINT, reviewer_user_id BIGINT,
 reviewed_at TIMESTAMP, created_at TIMESTAMP, updated_at TIMESTAMP
);
