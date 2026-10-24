-- Isolated school catalog schema, used with schema-test.sql; never run on a business database.
CREATE TABLE school (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100), province VARCHAR(50), level VARCHAR(50),
 created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE school_detail (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, school_id BIGINT, major_name VARCHAR(100), major_code VARCHAR(20),
 year INT, enrollment_count INT, score_line INT, remark VARCHAR(1000),
 created_at TIMESTAMP, updated_at TIMESTAMP
);
