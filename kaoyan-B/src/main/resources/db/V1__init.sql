SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id`             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username`       VARCHAR(64)     NOT NULL,
  `password_hash`  VARCHAR(100)    NOT NULL COMMENT 'BCrypt',
  `role`           VARCHAR(20)     NOT NULL DEFAULT 'STUDENT' COMMENT 'STUDENT/ADMIN',
  `status`         TINYINT         NOT NULL DEFAULT 1 COMMENT '1正常 0禁用',
  `avatar_url`     VARCHAR(500)    DEFAULT NULL COMMENT '头像 URL',
  `target_school`  VARCHAR(255)    DEFAULT NULL COMMENT '目标院校',
  `target_major`   VARCHAR(255)    DEFAULT NULL COMMENT '目标专业',
  `exam_year`      INT             DEFAULT NULL COMMENT '考试年份',
  `background`     TEXT            DEFAULT NULL COMMENT '考生背景',
  `created_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户账号与档案';

DROP TABLE IF EXISTS `task`;
CREATE TABLE `task` (
  `id`             VARCHAR(36)     NOT NULL COMMENT 'UUID',
  `user_id`        BIGINT UNSIGNED NOT NULL COMMENT '→ user.id',
  `task_type`      VARCHAR(50)     NOT NULL COMMENT 'KNOWLEDGE_QA/SCHOOL_RECOMMEND',
  `status`         VARCHAR(20)     NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING/RUNNING/SUCCESS/FAILED',
  `input_payload`  JSON            DEFAULT NULL COMMENT '请求参数',
  `result_payload` JSON            DEFAULT NULL COMMENT 'Agent 返回结果',
  `release_id`     VARCHAR(64)     DEFAULT NULL COMMENT '版本标识',
  `error_message`  TEXT            DEFAULT NULL COMMENT '失败原因',
  `created_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_task_user_created` (`user_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent 任务';

DROP TABLE IF EXISTS `document`;
CREATE TABLE `document` (
  `id`               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `title`            VARCHAR(255)    NOT NULL,
  `subject`          VARCHAR(20)     NOT NULL COMMENT '数据结构/操作系统/计算机网络/计算机组成原理',
  `content`          TEXT            NOT NULL,
  `source_url`       VARCHAR(500)    DEFAULT NULL,
  `status`           VARCHAR(20)     NOT NULL DEFAULT 'DRAFT' COMMENT 'DRAFT/PENDING_REVIEW/PUBLISHED/REJECTED',
  `creator_user_id`  BIGINT UNSIGNED DEFAULT NULL COMMENT '→ user.id',
  `reviewer_user_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '→ user.id',
  `reviewed_at`      DATETIME        DEFAULT NULL,
  `created_at`       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_doc_subject_status` (`subject`, `status`),
  KEY `idx_doc_creator` (`creator_user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='备考资料';

DROP TABLE IF EXISTS `school`;
CREATE TABLE `school` (
  `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name`       VARCHAR(255)    NOT NULL,
  `province`   VARCHAR(50)     DEFAULT NULL,
  `level`      VARCHAR(20)     DEFAULT NULL COMMENT '985/211/双一流',
  `created_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_school_province` (`province`),
  KEY `idx_school_level` (`level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='院校基础信息';

DROP TABLE IF EXISTS `school_detail`;
CREATE TABLE `school_detail` (
  `id`               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `school_id`        BIGINT UNSIGNED NOT NULL COMMENT '→ school.id',
  `major_name`       VARCHAR(255)    NOT NULL COMMENT '专业名',
  `major_code`       VARCHAR(50)     DEFAULT NULL COMMENT '专业代码',
  `year`             INT             NOT NULL COMMENT '招生年份',
  `enrollment_count` INT             DEFAULT NULL COMMENT '招生人数',
  `score_line`       INT             DEFAULT NULL COMMENT '复试分数线',
  `remark`           TEXT            DEFAULT NULL COMMENT '备注',
  `created_at`       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_detail_school` (`school_id`),
  KEY `idx_detail_school_year` (`school_id`, `year`),
  KEY `idx_detail_major_code` (`major_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='院校专业与分数线详情';

DROP TABLE IF EXISTS `recommend_record`;
CREATE TABLE `recommend_record` (
  `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`    BIGINT UNSIGNED NOT NULL COMMENT '→ user.id',
  `school_id`  BIGINT UNSIGNED NOT NULL COMMENT '→ school.id',
  `reason`     TEXT            DEFAULT NULL COMMENT '推荐理由',
  `score`      DECIMAL(5,2)    DEFAULT NULL COMMENT '匹配分',
  `created_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_recommend_user` (`user_id`),
  KEY `idx_recommend_school` (`school_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='择校推荐记录';

DROP TABLE IF EXISTS `question`;
CREATE TABLE `question` (
  `id`                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `subject`           VARCHAR(20)     NOT NULL,
  `knowledge_point`   VARCHAR(255)    DEFAULT NULL COMMENT '知识点',
  `content`           TEXT            NOT NULL COMMENT '题干',
  `option_a`          TEXT            DEFAULT NULL,
  `option_b`          TEXT            DEFAULT NULL,
  `option_c`          TEXT            DEFAULT NULL,
  `option_d`          TEXT            DEFAULT NULL,
  `answer`            VARCHAR(10)     NOT NULL COMMENT '正确答案',
  `analysis`          TEXT            DEFAULT NULL COMMENT '解析',
  `difficulty`        VARCHAR(10)     NOT NULL DEFAULT 'MEDIUM' COMMENT 'EASY/MEDIUM/HARD',
  `question_type`     VARCHAR(20)     NOT NULL DEFAULT 'SINGLE_CHOICE',
  `version`           INT             NOT NULL DEFAULT 1,
  `active`            TINYINT         NOT NULL DEFAULT 1,
  `stable_order`      INT             NOT NULL DEFAULT 0,
  `review_status`     VARCHAR(20)     NOT NULL DEFAULT 'PENDING_REVIEW' COMMENT 'PENDING_REVIEW/APPROVED/REJECTED',
  `reviewer_user_id`  BIGINT UNSIGNED DEFAULT NULL COMMENT '→ user.id',
  `reviewed_at`       DATETIME        DEFAULT NULL,
  `review_comment`    TEXT            DEFAULT NULL,
  `created_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_question_subject_active` (`subject`, `active`),
  KEY `idx_question_difficulty` (`difficulty`),
  KEY `idx_question_review_status` (`review_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='题库';

DROP TABLE IF EXISTS `practice_record`;
CREATE TABLE `practice_record` (
  `id`             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`        BIGINT UNSIGNED NOT NULL COMMENT '→ user.id',
  `session_id`     VARCHAR(36)     NOT NULL COMMENT '一次刷题批次',
  `question_id`    BIGINT UNSIGNED NOT NULL COMMENT '→ question.id',
  `order_index`    INT             NOT NULL DEFAULT 0,
  `user_answer`    VARCHAR(10)     DEFAULT NULL,
  `is_correct`     TINYINT         DEFAULT NULL,
  `grading_status` VARCHAR(20)     NOT NULL DEFAULT 'valid',
  `answered_at`    DATETIME        DEFAULT NULL,
  `created_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_practice_session_question` (`session_id`, `question_id`),
  KEY `idx_practice_user` (`user_id`),
  KEY `idx_practice_question` (`question_id`),
  KEY `idx_practice_session` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='刷题记录';

DROP TABLE IF EXISTS `user_question_mark`;
CREATE TABLE `user_question_mark` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`       BIGINT UNSIGNED NOT NULL COMMENT '→ user.id',
  `question_id`   BIGINT UNSIGNED NOT NULL COMMENT '→ question.id',
  `is_favorite`   TINYINT         NOT NULL DEFAULT 0,
  `is_wrong`      TINYINT         NOT NULL DEFAULT 0,
  `wrong_count`    INT             NOT NULL DEFAULT 0,
  `last_wrong_at` DATETIME        DEFAULT NULL,
  `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_mark_user_question` (`user_id`, `question_id`),
  KEY `idx_mark_user_wrong` (`user_id`, `is_wrong`),
  KEY `idx_mark_user_favorite` (`user_id`, `is_favorite`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='错题与收藏';

DROP TABLE IF EXISTS `study_stat`;
CREATE TABLE `study_stat` (
  `id`             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`        BIGINT UNSIGNED NOT NULL COMMENT '→ user.id',
  `stat_date`      DATE            NOT NULL,
  `question_count` INT             NOT NULL DEFAULT 0,
  `correct_count`  INT             NOT NULL DEFAULT 0,
  `study_minutes`  INT             NOT NULL DEFAULT 0,
  `created_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_stat_user_date` (`user_id`, `stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='每日学习统计';

SET FOREIGN_KEY_CHECKS = 1;
