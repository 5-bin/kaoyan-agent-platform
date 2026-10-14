-- ============================================================
-- 为 user_id=3（测试账号）补一些业务数据
-- 在 kaoyan 库执行：SOURCE 这个文件
-- 用 INSERT IGNORE 避免重复执行报错
-- ============================================================
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------- 1. task（Agent 任务） ----------
INSERT IGNORE INTO `task`
  (`id`, `user_id`, `task_type`, `status`, `input_payload`, `result_payload`, `release_id`, `error_message`)
VALUES
  ('a0000001-0000-0000-0000-000000000001', 3, 'KNOWLEDGE_QA', 'SUCCESS',
   JSON_OBJECT('question', '进程和线程的区别是什么'),
   JSON_OBJECT('answer', '进程是资源分配的最小单位，线程是CPU调度的最小单位...'),
   'v1.0.0', NULL),
  ('a0000001-0000-0000-0000-000000000002', 3, 'SCHOOL_RECOMMEND', 'SUCCESS',
   JSON_OBJECT('score_line', 340, 'major', '计算机'),
   JSON_OBJECT('schools', JSON_ARRAY('福州大学', '厦门大学')),
   'v1.0.0', NULL);

-- ---------- 2. document（备考资料，creator 指向 user 3） ----------
INSERT IGNORE INTO `document`
  (`title`, `subject`, `content`, `source_url`, `status`, `creator_user_id`, `reviewer_user_id`, `reviewed_at`)
VALUES
  ('计网高频考点整理', '计算机网络',
   'OSI七层模型、TCP三次握手四次挥手、HTTP与HTTPS区别...',
   'https://example.com/net2', 'PUBLISHED', 3, 1, NOW()),
  ('操作系统错题回顾', '操作系统',
   '进程调度算法、死锁条件、内存分页分段...',
   'https://example.com/os2', 'PENDING_REVIEW', 3, NULL, NULL);

-- ---------- 3. school（院校基础，补一所） ----------
INSERT IGNORE INTO `school` (`id`, `name`, `province`, `level`) VALUES
  (6, '南昌大学', '江西', '211');

-- ---------- 4. school_detail（院校专业分数线，补一行） ----------
INSERT IGNORE INTO `school_detail`
  (`school_id`, `major_name`, `major_code`, `year`, `enrollment_count`, `score_line`, `remark`)
VALUES
  (6, '计算机科学与技术', '081200', 2025, 45, 310, '信息工程学院');

-- ---------- 5. recommend_record（择校推荐记录） ----------
INSERT IGNORE INTO `recommend_record`
  (`user_id`, `school_id`, `reason`, `score`)
VALUES
  (3, 1, '分数线匹配、计算机学科强，推荐冲刺', 88.50),
  (3, 5, '本地211、分数线较稳妥，推荐保底', 76.00),
  (3, 6, '竞争相对小、招生人数多，推荐备选', 70.25);

-- ---------- 6. question（题库，补一道） ----------
INSERT IGNORE INTO `question`
  (`id`, `subject`, `knowledge_point`, `content`,
   `option_a`, `option_b`, `option_c`, `option_d`,
   `answer`, `analysis`, `difficulty`, `question_type`,
   `version`, `active`, `stable_order`, `review_status`, `reviewer_user_id`, `reviewed_at`)
VALUES
  (6, '数据结构', '排序',
   '下列排序算法中，平均时间复杂度为 O(nlogn) 的是？',
   '冒泡排序', '快速排序', '直接插入排序', '选择排序',
   'B', '快排平均O(nlogn)，最坏O(n^2)', 'MEDIUM', 'SINGLE_CHOICE',
   1, 1, 6, 'APPROVED', 1, NOW());

-- ---------- 7. practice_record（刷题记录，同一次 session） ----------
INSERT IGNORE INTO `practice_record`
  (`user_id`, `session_id`, `question_id`, `order_index`, `user_answer`, `is_correct`, `grading_status`, `answered_at`)
VALUES
  (3, 'sess-user3-0001', 1, 0, 'B', 1, 'valid', NOW()),
  (3, 'sess-user3-0001', 2, 1, 'D', 1, 'valid', NOW()),
  (3, 'sess-user3-0001', 3, 2, 'SYN', 0, 'valid', NOW());

-- ---------- 8. user_question_mark（错题/收藏） ----------
INSERT IGNORE INTO `user_question_mark`
  (`user_id`, `question_id`, `is_favorite`, `is_wrong`, `wrong_count`, `last_wrong_at`)
VALUES
  (3, 3, 0, 1, 1, NOW()),
  (3, 1, 1, 0, 0, NULL);

-- ---------- 9. study_stat（每日学习统计） ----------
INSERT IGNORE INTO `study_stat`
  (`user_id`, `stat_date`, `question_count`, `correct_count`, `study_minutes`)
VALUES
  (3, CURDATE(),        3, 2, 45),
  (3, DATE_SUB(CURDATE(), INTERVAL 1 DAY),  8, 6, 90),
  (3, DATE_SUB(CURDATE(), INTERVAL 2 DAY),  5, 4, 60);

-- ---------- 10. user：确保 user 3 存在（若你已注册过则 IGNORE 跳过） ----------
INSERT IGNORE INTO `user`
  (`id`, `username`, `password_hash`, `role`, `status`, `target_school`, `target_major`, `exam_year`, `background`)
VALUES
  (3, 'test3',
   '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iKTVKIUi',
   'STUDENT', 1, '福州大学', '计算机技术', 2026, '测试账号');

SET FOREIGN_KEY_CHECKS = 1;
