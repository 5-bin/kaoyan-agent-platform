-- 密码统一为 password，BCrypt 哈希
INSERT IGNORE INTO `user`
  (`id`, `username`, `password_hash`, `role`, `status`, `avatar_url`,
   `target_school`, `target_major`, `exam_year`, `background`)
VALUES
  (1, 'admin',
   '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iKTVKIUi',
   'ADMIN', 1, NULL, NULL, NULL, NULL, NULL),
  (2, 'student',
   '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iKTVKIUi',
   'STUDENT', 1, NULL, '清华大学', '计算机科学与技术', 2026,
   '本科计算机，想冲 985');

INSERT IGNORE INTO `school` (`id`, `name`, `province`, `level`) VALUES
  (1, '清华大学',   '北京', '985'),
  (2, '北京大学',   '北京', '985'),
  (3, '浙江大学',   '浙江', '985'),
  (4, '厦门大学',   '福建', '985'),
  (5, '福州大学',   '福建', '211');

INSERT IGNORE INTO `school_detail`
  (`school_id`, `major_name`, `major_code`, `year`,
   `enrollment_count`, `score_line`, `remark`)
VALUES
  (1, '计算机科学与技术', '081200', 2025, 30, 380, '计算机系'),
  (1, '软件工程',         '083500', 2025, 20, 370, '软件学院'),
  (2, '计算机科学与技术', '081200', 2025, 35, 375, '信息科学技术学院'),
  (3, '计算机科学与技术', '081200', 2025, 40, 360, '计算机学院'),
  (4, '计算机科学与技术', '081200', 2025, 25, 350, '信息学院'),
  (5, '计算机技术',       '085400', 2025, 60, 320, '计算机与大数据学院');

INSERT IGNORE INTO `question`
  (`id`, `subject`, `knowledge_point`, `content`,
   `option_a`, `option_b`, `option_c`, `option_d`,
   `answer`, `analysis`, `difficulty`, `question_type`,
   `version`, `active`, `stable_order`, `review_status`)
VALUES
  (1, '数据结构', '线性表',
   '在长度为 n 的顺序表第 i 个位置插入一个元素，需要移动的元素个数是？',
   'n-i', 'n-i+1', 'n-i-1', 'i',
   'B', '第 i 个位置插入，需要移动 n-i+1 个元素',
   'EASY', 'SINGLE_CHOICE', 1, 1, 1, 'APPROVED'),
  (2, '操作系统', '进程管理',
   '下列哪个不是进程的基本状态？',
   '就绪', '运行', '阻塞', '等待',
   'D', '进程三种基本状态：就绪、运行、阻塞',
   'EASY', 'SINGLE_CHOICE', 1, 1, 2, 'APPROVED'),
  (3, '计算机网络', 'TCP',
   'TCP 三次握手中，第二次握手发送的报文段标志位是？',
   'SYN', 'ACK', 'SYN+ACK', 'FIN',
   'C', '第二次握手服务端回复 SYN+ACK',
   'MEDIUM', 'SINGLE_CHOICE', 1, 1, 3, 'APPROVED'),
  (4, '计算机组成原理', '存储器',
   'Cache 与主存之间的地址映射方式不包括？',
   '直接映射', '全相联映射', '组相联映射', '页式映射',
   'D', 'Cache 三种映射：直接、全相联、组相联',
   'EASY', 'SINGLE_CHOICE', 1, 1, 4, 'APPROVED'),
  (5, '数据结构', '树',
   '含有 n 个结点的完全二叉树的高度是？',
   'log2(n)', 'log2(n)+1', 'floor(log2(n))+1', 'ceil(log2(n+1))',
   'C', '完全二叉树高度为 floor(log2(n))+1',
   'MEDIUM', 'SINGLE_CHOICE', 1, 1, 5, 'APPROVED');

INSERT IGNORE INTO `document`
  (`id`, `title`, `subject`, `content`, `source_url`,
   `status`, `creator_user_id`, `reviewer_user_id`, `reviewed_at`)
VALUES
  (1, '数据结构核心考点', '数据结构',
   '线性表、栈、队列、树、图、查找、排序...',
   'https://example.com/ds', 'PUBLISHED', 1, 1, NOW()),
  (2, '操作系统重点章节', '操作系统',
   '进程管理、内存管理、文件系统、IO...',
   'https://example.com/os', 'PUBLISHED', 1, 1, NOW()),
  (3, '计算机网络考点梳理', '计算机网络',
   'OSI 七层、TCP/IP、HTTP、DNS...',
   'https://example.com/net', 'PUBLISHED', 1, 1, NOW()),
  (4, '计算机组成原理重点', '计算机组成原理',
   '数据表示、运算器、存储器、指令系统...',
   'https://example.com/co', 'PENDING_REVIEW', 1, NULL, NULL);
