-- 考研 Agent 服务数据库初始化
-- 说明：Agent 与 Spring Boot 后端共用同一个 kaoyan 数据库，
-- 只读 question 表，不另建业务库。
-- 该脚本仅用于确认库和 question 表存在；question 表结构由后端 Flyway 维护。

CREATE DATABASE IF NOT EXISTS kaoyan DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE kaoyan;

-- 验证：
-- SHOW TABLES;
-- SELECT COUNT(*) FROM question;
