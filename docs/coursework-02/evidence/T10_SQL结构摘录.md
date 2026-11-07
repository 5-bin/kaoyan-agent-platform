# T10 SQL 结构摘录（V1 基线 / V7—V15 增量）

> 任务：Issue #28 · 负责人 S3 · 交付位置 `docs/coursework-02/evidence/T10_SQL结构摘录.md`
> 事实来源：`kaoyan-B/src/main/resources/db/`（第 1 节读 `V1__init.sql`；第 2 节读 `V7`—`V15`）
> 设计基线：`94b8a9f`；行号取 `7c9ab82` 工作树（两者之间 `db/` 无差异，已核对）
> 生成方式：静态阅读 SQL 原文并逐条摘录，**未连接数据库、未执行任何 SQL**；只记录原文语义，不判定 ER、外键或事务。
> 配套文档（同图产出）：`T10_迁移索引.md`（版本与变更定位）。

## 0. 一页速览

| 项 | 数值 | 说明 |
|---|---|---|
| 建表合计 | **28 张** | V1 10 + V10 3 + V11 2 + V12 2 + V13 10 + V14 1 |
| 字段合计 | **264 个** | V1 103 + 新表 152 + 既有表改列 9 |
| 主键 | 28 | 每表都有；复合主键 5 个（见 2.4、2.6、2.7） |
| 唯一键 | 11 | V1 4 + 增量 7 |
| 普通索引 | 25 | V1 18 + 增量 7 |
| 显式 FOREIGN KEY | 1 | V14 `fk_admission_detail` |
| CHECK 约束 | 4 | V14 3 + V15 1 |
| 表选项 | 11 张显式 InnoDB/utf8mb4 | V1 10 + V14；V10—V13 的 17 张未写，依赖服务器默认 |
| 版本文件 | 15 个 | V1—V15；V2—V6 无 DDL |

> 范围：第 1 节 V1 基线（10 表），第 2 节 V7—V15 增量（18 张新表 + 9 处改列 + 5 个约束）。V2—V6 是旧演示种子、不建表；**28 表均来自 V1/V10—V14**，详见 `T10_迁移索引.md`。

## 1. V1 基线（10 张表）

### 1.1 文件头与全局约定

| 行 | 语句 | 说明 |
|---|---|---|
| 1 | `SET NAMES utf8mb4;` | 会话字符集 |
| 2 | `SET FOREIGN_KEY_CHECKS = 0;` | 建表期间关闭外键检查 |
| 4 / 22 / 38 / 56 / 69 / 87 / 100 / 129 / 148 / 165 | `DROP TABLE IF EXISTS ...`（10 条） | 每表先删后建；V1 含 DROP，**不得在已有业务库重跑** |
| 179 | `SET FOREIGN_KEY_CHECKS = 1;` | 恢复外键检查 |

- 10 张表统一 `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`；未声明 `COLLATE`、`ROW_FORMAT`、分区、触发器或存储过程。
- V1 没有 `BEGIN`/`COMMIT`，不声明事务边界。
- 索引全部写在 `CREATE TABLE` 内（无独立 `CREATE INDEX`）。
- 所有 `CREATE TABLE` 都没有 `IF NOT EXISTS`。

### 1.2 `user` · 用户账号与档案（12 字段）

- 定义：`V1__init.sql:5`（`DROP` 在 :4）；表注释：`用户账号与档案`。

| # | 字段 | 类型 | 可空 | 默认 | 注释 / 逻辑引用 |
|---|---|---|---|---|---|
| 1 | `id` | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | — |
| 2 | `username` | VARCHAR(64) | 否 | — | — |
| 3 | `password_hash` | VARCHAR(100) | 否 | — | BCrypt |
| 4 | `role` | VARCHAR(20) | 否 | `'STUDENT'` | STUDENT/ADMIN |
| 5 | `status` | TINYINT | 否 | 1 | 1正常 0禁用 |
| 6 | `avatar_url` | VARCHAR(500) | 是 | NULL | 头像 URL |
| 7 | `target_school` | VARCHAR(255) | 是 | NULL | 目标院校 |
| 8 | `target_major` | VARCHAR(255) | 是 | NULL | 目标专业 |
| 9 | `exam_year` | INT | 是 | NULL | 考试年份 |
| 10 | `background` | TEXT | 是 | NULL | 考生背景 |
| 11 | `created_at` | DATETIME | 否 | CURRENT_TIMESTAMP | — |
| 12 | `updated_at` | DATETIME | 否 | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | — |

- 键：`PRIMARY KEY (id)` :18；`UNIQUE KEY uk_user_username (username)` :19。
- 表选项：`ENGINE=InnoDB DEFAULT CHARSET=utf8mb4` :20。

### 1.3 `task` · Agent 任务（10 字段）

- 定义：`V1__init.sql:23`（`DROP` 在 :22）；表注释：`Agent 任务`。

| # | 字段 | 类型 | 可空 | 默认 | 注释 / 逻辑引用 |
|---|---|---|---|---|---|
| 1 | `id` | VARCHAR(36) | 否 | — | UUID |
| 2 | `user_id` | BIGINT UNSIGNED | 否 | — | → user.id |
| 3 | `task_type` | VARCHAR(50) | 否 | — | KNOWLEDGE_QA/SCHOOL_RECOMMEND |
| 4 | `status` | VARCHAR(20) | 否 | `'PENDING'` | PENDING/RUNNING/SUCCESS/FAILED |
| 5 | `input_payload` | JSON | 是 | NULL | 请求参数 |
| 6 | `result_payload` | JSON | 是 | NULL | Agent 返回结果 |
| 7 | `release_id` | VARCHAR(64) | 是 | NULL | 版本标识 |
| 8 | `error_message` | TEXT | 是 | NULL | 失败原因 |
| 9 | `created_at` | DATETIME | 否 | CURRENT_TIMESTAMP | — |
| 10 | `updated_at` | DATETIME | 否 | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | — |

- 键：`PRIMARY KEY (id)` :34；`KEY idx_task_user_created (user_id, created_at)` :35。
- 表选项：`ENGINE=InnoDB DEFAULT CHARSET=utf8mb4` :36。

### 1.4 `document` · 备考资料（11 字段）

- 定义：`V1__init.sql:39`（`DROP` 在 :38）；表注释：`备考资料`。

| # | 字段 | 类型 | 可空 | 默认 | 注释 / 逻辑引用 |
|---|---|---|---|---|---|
| 1 | `id` | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | — |
| 2 | `title` | VARCHAR(255) | 否 | — | — |
| 3 | `subject` | VARCHAR(20) | 否 | — | 数据结构/操作系统/计算机网络/计算机组成原理 |
| 4 | `content` | TEXT | 否 | — | — |
| 5 | `source_url` | VARCHAR(500) | 是 | NULL | — |
| 6 | `status` | VARCHAR(20) | 否 | `'DRAFT'` | DRAFT/PENDING_REVIEW/PUBLISHED/REJECTED |
| 7 | `creator_user_id` | BIGINT UNSIGNED | 是 | NULL | → user.id |
| 8 | `reviewer_user_id` | BIGINT UNSIGNED | 是 | NULL | → user.id |
| 9 | `reviewed_at` | DATETIME | 是 | NULL | — |
| 10 | `created_at` | DATETIME | 否 | CURRENT_TIMESTAMP | — |
| 11 | `updated_at` | DATETIME | 否 | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | — |

- 键：`PRIMARY KEY (id)` :51；`KEY idx_doc_subject_status (subject, status)` :52；`KEY idx_doc_creator (creator_user_id)` :53。
- 表选项：`ENGINE=InnoDB DEFAULT CHARSET=utf8mb4` :54。

### 1.5 `school` · 院校基础信息（6 字段）

- 定义：`V1__init.sql:57`（`DROP` 在 :56）；表注释：`院校基础信息`。

| # | 字段 | 类型 | 可空 | 默认 | 注释 / 逻辑引用 |
|---|---|---|---|---|---|
| 1 | `id` | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | — |
| 2 | `name` | VARCHAR(255) | 否 | — | — |
| 3 | `province` | VARCHAR(50) | 是 | NULL | — |
| 4 | `level` | VARCHAR(20) | 是 | NULL | 985/211/双一流 |
| 5 | `created_at` | DATETIME | 否 | CURRENT_TIMESTAMP | — |
| 6 | `updated_at` | DATETIME | 否 | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | — |

- 键：`PRIMARY KEY (id)` :64；`KEY idx_school_province (province)` :65；`KEY idx_school_level (level)` :66。
- 表选项：`ENGINE=InnoDB DEFAULT CHARSET=utf8mb4` :67。

### 1.6 `school_detail` · 院校专业与分数线详情（10 字段）

- 定义：`V1__init.sql:70`（`DROP` 在 :69）；表注释：`院校专业与分数线详情`。

| # | 字段 | 类型 | 可空 | 默认 | 注释 / 逻辑引用 |
|---|---|---|---|---|---|
| 1 | `id` | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | — |
| 2 | `school_id` | BIGINT UNSIGNED | 否 | — | → school.id |
| 3 | `major_name` | VARCHAR(255) | 否 | — | 专业名 |
| 4 | `major_code` | VARCHAR(50) | 是 | NULL | 专业代码 |
| 5 | `year` | INT | 否 | — | 招生年份 |
| 6 | `enrollment_count` | INT | 是 | NULL | 招生人数 |
| 7 | `score_line` | INT | 是 | NULL | 复试分数线 |
| 8 | `remark` | TEXT | 是 | NULL | 备注 |
| 9 | `created_at` | DATETIME | 否 | CURRENT_TIMESTAMP | — |
| 10 | `updated_at` | DATETIME | 否 | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | — |

- 键：`PRIMARY KEY (id)` :81；`KEY idx_detail_school (school_id)` :82；`KEY idx_detail_school_year (school_id, year)` :83；`KEY idx_detail_major_code (major_code)` :84。
- 表选项：`ENGINE=InnoDB DEFAULT CHARSET=utf8mb4` :85。

### 1.7 `recommend_record` · 择校推荐记录（6 字段）

- 定义：`V1__init.sql:88`（`DROP` 在 :87）；表注释：`择校推荐记录`。

| # | 字段 | 类型 | 可空 | 默认 | 注释 / 逻辑引用 |
|---|---|---|---|---|---|
| 1 | `id` | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | — |
| 2 | `user_id` | BIGINT UNSIGNED | 否 | — | → user.id |
| 3 | `school_id` | BIGINT UNSIGNED | 否 | — | → school.id |
| 4 | `reason` | TEXT | 是 | NULL | 推荐理由 |
| 5 | `score` | DECIMAL(5,2) | 是 | NULL | 匹配分 |
| 6 | `created_at` | DATETIME | 否 | CURRENT_TIMESTAMP | — |

- 键：`PRIMARY KEY (id)` :95；`KEY idx_recommend_user (user_id)` :96；`KEY idx_recommend_school (school_id)` :97。
- 表选项：`ENGINE=InnoDB DEFAULT CHARSET=utf8mb4` :98。

### 1.8 `question` · 题库（21 字段）

- 定义：`V1__init.sql:101`（`DROP` 在 :100）；表注释：`题库`。

| # | 字段 | 类型 | 可空 | 默认 | 注释 / 逻辑引用 |
|---|---|---|---|---|---|
| 1 | `id` | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | — |
| 2 | `subject` | VARCHAR(20) | 否 | — | — |
| 3 | `knowledge_point` | VARCHAR(255) | 是 | NULL | 知识点 |
| 4 | `content` | TEXT | 否 | — | 题干 |
| 5 | `option_a` | TEXT | 是 | NULL | — |
| 6 | `option_b` | TEXT | 是 | NULL | — |
| 7 | `option_c` | TEXT | 是 | NULL | — |
| 8 | `option_d` | TEXT | 是 | NULL | — |
| 9 | `answer` | VARCHAR(10) | 否 | — | 正确答案 |
| 10 | `analysis` | TEXT | 是 | NULL | 解析 |
| 11 | `difficulty` | VARCHAR(10) | 否 | `'MEDIUM'` | EASY/MEDIUM/HARD |
| 12 | `question_type` | VARCHAR(20) | 否 | `'SINGLE_CHOICE'` | — |
| 13 | `version` | INT | 否 | 1 | — |
| 14 | `active` | TINYINT | 否 | 1 | — |
| 15 | `stable_order` | INT | 否 | 0 | — |
| 16 | `review_status` | VARCHAR(20) | 否 | `'PENDING_REVIEW'` | PENDING_REVIEW/APPROVED/REJECTED |
| 17 | `reviewer_user_id` | BIGINT UNSIGNED | 是 | NULL | → user.id |
| 18 | `reviewed_at` | DATETIME | 是 | NULL | — |
| 19 | `review_comment` | TEXT | 是 | NULL | — |
| 20 | `created_at` | DATETIME | 否 | CURRENT_TIMESTAMP | — |
| 21 | `updated_at` | DATETIME | 否 | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | — |

- 键：`PRIMARY KEY (id)` :123；`KEY idx_question_subject_active (subject, active)` :124；`KEY idx_question_difficulty (difficulty)` :125；`KEY idx_question_review_status (review_status)` :126。
- 表选项：`ENGINE=InnoDB DEFAULT CHARSET=utf8mb4` :127。

### 1.9 `practice_record` · 刷题记录（10 字段）

- 定义：`V1__init.sql:130`（`DROP` 在 :129）；表注释：`刷题记录`。

| # | 字段 | 类型 | 可空 | 默认 | 注释 / 逻辑引用 |
|---|---|---|---|---|---|
| 1 | `id` | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | — |
| 2 | `user_id` | BIGINT UNSIGNED | 否 | — | → user.id |
| 3 | `session_id` | VARCHAR(36) | 否 | — | 一次刷题批次 |
| 4 | `question_id` | BIGINT UNSIGNED | 否 | — | → question.id |
| 5 | `order_index` | INT | 否 | 0 | — |
| 6 | `user_answer` | VARCHAR(10) | 是 | NULL | — |
| 7 | `is_correct` | TINYINT | 是 | NULL | — |
| 8 | `grading_status` | VARCHAR(20) | 否 | `'valid'` | — |
| 9 | `answered_at` | DATETIME | 是 | NULL | — |
| 10 | `created_at` | DATETIME | 否 | CURRENT_TIMESTAMP | — |

- 键：`PRIMARY KEY (id)` :141；`UNIQUE KEY uk_practice_session_question (session_id, question_id)` :142；`KEY idx_practice_user (user_id)` :143；`KEY idx_practice_question (question_id)` :144；`KEY idx_practice_session (session_id)` :145。
- 表选项：`ENGINE=InnoDB DEFAULT CHARSET=utf8mb4` :146。

### 1.10 `user_question_mark` · 错题与收藏（9 字段）

- 定义：`V1__init.sql:149`（`DROP` 在 :148）；表注释：`错题与收藏`。

| # | 字段 | 类型 | 可空 | 默认 | 注释 / 逻辑引用 |
|---|---|---|---|---|---|
| 1 | `id` | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | — |
| 2 | `user_id` | BIGINT UNSIGNED | 否 | — | → user.id |
| 3 | `question_id` | BIGINT UNSIGNED | 否 | — | → question.id |
| 4 | `is_favorite` | TINYINT | 否 | 0 | — |
| 5 | `is_wrong` | TINYINT | 否 | 0 | — |
| 6 | `wrong_count` | INT | 否 | 0 | — |
| 7 | `last_wrong_at` | DATETIME | 是 | NULL | — |
| 8 | `created_at` | DATETIME | 否 | CURRENT_TIMESTAMP | — |
| 9 | `updated_at` | DATETIME | 否 | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | — |

- 键：`PRIMARY KEY (id)` :159；`UNIQUE KEY uk_mark_user_question (user_id, question_id)` :160；`KEY idx_mark_user_wrong (user_id, is_wrong)` :161；`KEY idx_mark_user_favorite (user_id, is_favorite)` :162。
- 表选项：`ENGINE=InnoDB DEFAULT CHARSET=utf8mb4` :163。

### 1.11 `study_stat` · 每日学习统计（8 字段）

- 定义：`V1__init.sql:166`（`DROP` 在 :165）；表注释：`每日学习统计`。

| # | 字段 | 类型 | 可空 | 默认 | 注释 / 逻辑引用 |
|---|---|---|---|---|---|
| 1 | `id` | BIGINT UNSIGNED | 否 | AUTO_INCREMENT | — |
| 2 | `user_id` | BIGINT UNSIGNED | 否 | — | → user.id |
| 3 | `stat_date` | DATE | 否 | — | — |
| 4 | `question_count` | INT | 否 | 0 | — |
| 5 | `correct_count` | INT | 否 | 0 | — |
| 6 | `study_minutes` | INT | 否 | 0 | — |
| 7 | `created_at` | DATETIME | 否 | CURRENT_TIMESTAMP | — |
| 8 | `updated_at` | DATETIME | 否 | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | — |

- 键：`PRIMARY KEY (id)` :175；`UNIQUE KEY uk_stat_user_date (user_id, stat_date)` :176。
- 表选项：`ENGINE=InnoDB DEFAULT CHARSET=utf8mb4` :177。

### 1.12 基线一览（10 表汇总）

| 表 | 定义行 | 字段 | 主键 | 唯一键 | 普通索引 | 表注释 |
|---|---|---|---|---|---|---|
| `user` | :5 | 12 | id | `uk_user_username` | 0 | 用户账号与档案 |
| `task` | :23 | 10 | id | — | `idx_task_user_created` | Agent 任务 |
| `document` | :39 | 11 | id | — | `idx_doc_subject_status`、`idx_doc_creator` | 备考资料 |
| `school` | :57 | 6 | id | — | `idx_school_province`、`idx_school_level` | 院校基础信息 |
| `school_detail` | :70 | 10 | id | — | `idx_detail_school`、`idx_detail_school_year`、`idx_detail_major_code` | 院校专业与分数线详情 |
| `recommend_record` | :88 | 6 | id | — | `idx_recommend_user`、`idx_recommend_school` | 择校推荐记录 |
| `question` | :101 | 21 | id | — | `idx_question_subject_active`、`idx_question_difficulty`、`idx_question_review_status` | 题库 |
| `practice_record` | :130 | 10 | id | `uk_practice_session_question` | `idx_practice_user`、`idx_practice_question`、`idx_practice_session` | 刷题记录 |
| `user_question_mark` | :149 | 9 | id | `uk_mark_user_question` | `idx_mark_user_wrong`、`idx_mark_user_favorite` | 错题与收藏 |
| `study_stat` | :166 | 8 | id | `uk_stat_user_date` | 0 | 每日学习统计 |
| **合计** | — | **103** | **10** | **4** | **18** | — |

### 1.13 注释中的逻辑引用（不判定为外键）

| 表.字段 | 原注释 | 指向 | 行 |
|---|---|---|---|
| `task.user_id` | → user.id | `user.id` | 25 |
| `document.creator_user_id` | → user.id | `user.id` | 46 |
| `document.reviewer_user_id` | → user.id | `user.id` | 47 |
| `school_detail.school_id` | → school.id | `school.id` | 72 |
| `recommend_record.user_id` | → user.id | `user.id` | 90 |
| `recommend_record.school_id` | → school.id | `school.id` | 91 |
| `question.reviewer_user_id` | → user.id | `user.id` | 118 |
| `practice_record.user_id` | → user.id | `user.id` | 132 |
| `practice_record.question_id` | → question.id | `question.id` | 134 |
| `user_question_mark.user_id` | → user.id | `user.id` | 151 |
| `user_question_mark.question_id` | → question.id | `question.id` | 152 |
| `study_stat.user_id` | → user.id | `user.id` | 168 |

- 这 12 条只是字段 COMMENT 的原文；V1 没有对应的 `FOREIGN KEY` 声明。
- 引用分布：指向 `user` 8 条、`question` 2 条、`school` 2 条；`user` 与 `school` 自身没有向外引用的注释。

### 1.14 V1 未声明项（按原文）

- **没有 FOREIGN KEY / REFERENCES / ON DELETE / ON UPDATE 级联动作。**
- 没有 CHECK 约束、生成列、触发器、存储过程。
- 没有列级 COLLATE 或非 utf8mb4 字符集。
- 没有事务边界（`BEGIN`/`COMMIT`/`ROLLBACK`）。
- `DROP TABLE` 有 `IF EXISTS`，`CREATE TABLE` 没有 `IF NOT EXISTS`。
- 字段注释里的 `→ xxx.id` 不等于外键；ER 关系判断留给 T06。

---

## 2. V7—V15 增量（18 张新表、9 处改列、5 个约束）

> 本节覆盖 V7—V15 九个迁移文件，行号取当前工作树；V2—V6 不建表，见 2.9 与迁移索引。
> V10—V14 的新表字段均未写 COMMENT；V10—V13 的新表也未写 ENGINE/CHARSET 与表 COMMENT，下表不再重复空项。

### 2.1 版本总览

| 版本 | 文件 | 变更 | 对象 | 定义 |
|---|---|---|---|---|
| V7 | `V7__practice_snapshot.sql` | ALTER +1 列 | `practice_record.question_snapshot` | :2 |
| V8 | `V8__task_soft_delete.sql` | ALTER +1 列 | `task.deleted_at` | :2 |
| V9 | `V9__question_source.sql` | ALTER +6 列 | `question` 的 6 个 source 列 | :4、:6、:8、:10、:12、:14 |
| V10 | `V10__chat_conversation.sql` | CREATE 3 表 | `chat_conversation`、`chat_message`、`chat_generation` | :2、:8、:14 |
| V11 | `V11__personal_document.sql` | CREATE 2 表 | `personal_document`、`personal_document_version` | :1、:7 |
| V12 | `V12__assistant_privacy.sql` | CREATE 2 表 | `assistant_privacy`、`assistant_action` | :2、:8 |
| V13 | `V13__learning_loop.sql` | CREATE 10 表 | `practice_session` … `school_historical_metric` | :3—:50 |
| V14 | `V14__school_admission_metrics.sql` | CREATE 1 表 + 1 FK + 3 CHECK | `school_admission_metric` | :3 |
| V15 | `V15__profile_degree_type.sql` | ALTER +1 列 + 1 CHECK | `user.degree_type` | :3 |

### 2.2 既有表改列（V7、V8、V9）

| 版本 | 表 | 新增列 | 类型 | 可空 | 默认 | 注释（原文） | 定义 |
|---|---|---|---|---|---|---|---|
| V7 | `practice_record` | `question_snapshot` | JSON | 是 | NULL | Immutable question version captured at grading; legacy rows remain NULL | :2 |
| V8 | `task` | `deleted_at` | DATETIME | 是 | NULL | Hidden recommendation history; still counted toward task quotas | :2 |
| V9 | `question` | `source_type` | VARCHAR(20) | 是 | NULL | REAL_EXAM / MOCK / ORIGINAL; NULL for undocumented legacy sources | :4 |
| V9 | `question` | `source_name` | VARCHAR(255) | 是 | NULL | Paper, publication or original author record | :6 |
| V9 | `question` | `source_locator` | VARCHAR(1000) | 是 | NULL | Traceable URL, page, section or author record location | :8 |
| V9 | `question` | `source_year` | INT | 是 | NULL | Exam or source year when known | :10 |
| V9 | `question` | `source_question_no` | VARCHAR(64) | 是 | NULL | Original question number when applicable | :12 |
| V9 | `question` | `permission_note` | VARCHAR(2000) | 是 | NULL | Permission or original authorship evidence | :14 |

- 9 处改列全部可空、默认 NULL；V7/V8/V9 都没有删除或修改旧列。
- V15 的 `user.degree_type` 单独列在 2.8。

### 2.3 V10：聊天会话（3 表）

#### `chat_conversation`（8 字段）— `V10__chat_conversation.sql:2`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `id` | VARCHAR(36) | 否 | — |
| 2 | `user_id` | BIGINT | 否 | — |
| 3 | `title` | VARCHAR(100) | 否 | — |
| 4 | `conditions_json` | LONGTEXT | 否 | — |
| 5 | `profile_json` | LONGTEXT | 否 | — |
| 6 | `next_sequence` | INT | 否 | 1 |
| 7 | `created_at` | TIMESTAMP | 否 | CURRENT_TIMESTAMP |
| 8 | `updated_at` | TIMESTAMP | 否 | CURRENT_TIMESTAMP |

- 键：`PRIMARY KEY (id)` :3；`INDEX idx_conversation_owner (user_id, updated_at)` :6。
- 表选项：原文未写 `ENGINE`／`CHARSET`（依赖数据库默认）；`id` 为内联主键。

#### `chat_message`（7 字段）— `V10__chat_conversation.sql:8`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `id` | VARCHAR(36) | 否 | — |
| 2 | `conversation_id` | VARCHAR(36) | 否 | — |
| 3 | `user_id` | BIGINT | 否 | — |
| 4 | `sequence_no` | INT | 否 | — |
| 5 | `content` | TEXT | 否 | — |
| 6 | `document_id` | VARCHAR(36) | 是 | NULL |
| 7 | `created_at` | TIMESTAMP | 否 | CURRENT_TIMESTAMP |

- 键：`PRIMARY KEY (id)` :9；`UNIQUE KEY uq_message_sequence (conversation_id, sequence_no)` :12。

#### `chat_generation`（17 字段）— `V10__chat_conversation.sql:14`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `task_id` | VARCHAR(36) | 否 | — |
| 2 | `conversation_id` | VARCHAR(36) | 否 | — |
| 3 | `message_id` | VARCHAR(36) | 否 | — |
| 4 | `user_id` | BIGINT | 否 | — |
| 5 | `attempt_no` | INT | 否 | — |
| 6 | `client_request_id` | VARCHAR(64) | 否 | — |
| 7 | `request_hash` | VARCHAR(64) | 否 | — |
| 8 | `status` | VARCHAR(20) | 否 | — |
| 9 | `active_conversation_id` | VARCHAR(36) | 是 | NULL |
| 10 | `context_json` | LONGTEXT | 否 | — |
| 11 | `draft_json` | LONGTEXT | 否 | — |
| 12 | `result_json` | LONGTEXT | 是 | NULL |
| 13 | `version` | BIGINT | 否 | 0 |
| 14 | `stage` | VARCHAR(100) | 是 | NULL |
| 15 | `error_message` | VARCHAR(255) | 是 | NULL |
| 16 | `created_at` | TIMESTAMP | 否 | CURRENT_TIMESTAMP |
| 17 | `updated_at` | TIMESTAMP | 否 | CURRENT_TIMESTAMP |

- 键：`PRIMARY KEY (task_id)` :15；`UNIQUE KEY uq_generation_request (conversation_id, client_request_id)` :21；`UNIQUE KEY uq_generation_active (active_conversation_id)` :22；`UNIQUE KEY uq_generation_attempt (message_id, attempt_no)` :23；`INDEX idx_generation_conversation (conversation_id, created_at)` :24。

### 2.4 V11：个人文档（2 表）

#### `personal_document`（7 字段）— `V11__personal_document.sql:1`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `id` | VARCHAR(36) | 否 | — |
| 2 | `user_id` | BIGINT | 否 | — |
| 3 | `title` | VARCHAR(100) | 否 | — |
| 4 | `content` | LONGTEXT | 否 | — |
| 5 | `version` | INT | 否 | — |
| 6 | `created_at` | TIMESTAMP | 否 | CURRENT_TIMESTAMP |
| 7 | `updated_at` | TIMESTAMP | 否 | CURRENT_TIMESTAMP |

- 键：`PRIMARY KEY (id)` :2；`INDEX idx_personal_document_owner (user_id, updated_at)` :5。

#### `personal_document_version`（7 字段）— `V11__personal_document.sql:7`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `document_id` | VARCHAR(36) | 否 | — |
| 2 | `version` | INT | 否 | — |
| 3 | `user_id` | BIGINT | 否 | — |
| 4 | `title` | VARCHAR(100) | 否 | — |
| 5 | `content` | LONGTEXT | 否 | — |
| 6 | `source_task_id` | VARCHAR(36) | 是 | NULL |
| 7 | `created_at` | TIMESTAMP | 否 | CURRENT_TIMESTAMP |

- 键：`PRIMARY KEY (document_id, version)` :11；`UNIQUE KEY uq_document_source_task (source_task_id)` :11。

### 2.5 V12：助手隐私（2 表）

#### `assistant_privacy`（7 字段）— `V12__assistant_privacy.sql:2`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `user_id` | BIGINT | 否 | — |
| 2 | `model_allowed` | BOOLEAN | 否 | FALSE |
| 3 | `scopes_json` | LONGTEXT | 否 | — |
| 4 | `provider` | VARCHAR(500) | 否 | — |
| 5 | `version` | INT | 否 | 1 |
| 6 | `consented_at` | TIMESTAMP | 是 | NULL |
| 7 | `updated_at` | TIMESTAMP | 否 | CURRENT_TIMESTAMP |

- 键：`PRIMARY KEY (user_id)` :3。

#### `assistant_action`（10 字段）— `V12__assistant_privacy.sql:8`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `id` | VARCHAR(36) | 否 | — |
| 2 | `user_id` | BIGINT | 否 | — |
| 3 | `conversation_id` | VARCHAR(36) | 否 | — |
| 4 | `task_id` | VARCHAR(36) | 否 | — |
| 5 | `operation` | VARCHAR(32) | 否 | — |
| 6 | `status` | VARCHAR(20) | 否 | — |
| 7 | `payload_json` | LONGTEXT | 否 | — |
| 8 | `result_json` | LONGTEXT | 否 | — |
| 9 | `created_at` | TIMESTAMP | 否 | CURRENT_TIMESTAMP |
| 10 | `updated_at` | TIMESTAMP | 否 | CURRENT_TIMESTAMP |

- 键：`PRIMARY KEY (id)` :9；`UNIQUE (task_id)`（内联，未命名）:10；`INDEX idx_assistant_action_owner (user_id, created_at)` :13。

### 2.6 V13：学习闭环（10 表）

#### `practice_session`（9 字段）— `V13__learning_loop.sql:3`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `id` | VARCHAR(64) | 否 | — |
| 2 | `user_id` | BIGINT | 否 | — |
| 3 | `kind` | VARCHAR(20) | 否 | — |
| 4 | `state` | VARCHAR(20) | 否 | — |
| 5 | `revision` | INT | 否 | 0 |
| 6 | `current_index` | INT | 否 | 0 |
| 7 | `blueprint_json` | JSON | 否 | — |
| 8 | `created_at` | DATETIME | 否 | — |
| 9 | `finished_at` | DATETIME | 是 | NULL |

- 键：`PRIMARY KEY (id)` :4；`INDEX ix_session_owner (user_id, created_at)` :7。

#### `practice_session_item`（5 字段）— `V13__learning_loop.sql:9`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `record_id` | BIGINT | 否 | — |
| 2 | `session_id` | VARCHAR(64) | 否 | — |
| 3 | `hint_level` | INT | 否 | 0 |
| 4 | `draft_answer` | VARCHAR(10) | 是 | NULL |
| 5 | `submitted_at` | DATETIME | 是 | NULL |

- 键：`PRIMARY KEY (record_id)` :10；`INDEX ix_item_session (session_id)` :12。

#### `practice_request`（5 字段）— `V13__learning_loop.sql:14`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `user_id` | BIGINT | 否 | — |
| 2 | `request_id` | VARCHAR(64) | 否 | — |
| 3 | `fingerprint` | VARCHAR(64) | 否 | — |
| 4 | `response_json` | JSON | 否 | — |
| 5 | `created_at` | DATETIME | 否 | — |

- 键：`PRIMARY KEY (user_id, request_id)` :17。

#### `question_version`（6 字段）— `V13__learning_loop.sql:19`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `question_id` | BIGINT | 否 | — |
| 2 | `version` | INT | 否 | — |
| 3 | `snapshot_json` | JSON | 否 | — |
| 4 | `withdrawn` | INT | 否 | 0 |
| 5 | `withdrawal_reason` | VARCHAR(2000) | 是 | NULL |
| 6 | `created_at` | DATETIME | 否 | — |

- 键：`PRIMARY KEY (question_id, version)` :22。

#### `learning_blueprint`（5 字段）— `V13__learning_loop.sql:24`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `id` | VARCHAR(64) | 否 | — |
| 2 | `version` | INT | 否 | — |
| 3 | `config_json` | JSON | 否 | — |
| 4 | `reviewer_id` | BIGINT | 否 | — |
| 5 | `created_at` | DATETIME(6) | 否 | — |

- 键：`PRIMARY KEY (id)` :25。

#### `learning_profile`（4 字段）— `V13__learning_loop.sql:28`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `user_id` | BIGINT | 否 | — |
| 2 | `revision` | INT | 否 | 0 |
| 3 | `data_json` | JSON | 否 | — |
| 4 | `updated_at` | DATETIME | 否 | — |

- 键：`PRIMARY KEY (user_id)` :29。

#### `learning_profile_history`（4 字段）— `V13__learning_loop.sql:32`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `user_id` | BIGINT | 否 | — |
| 2 | `revision` | INT | 否 | — |
| 3 | `data_json` | JSON | 否 | — |
| 4 | `created_at` | DATETIME | 否 | — |

- 键：`PRIMARY KEY (user_id, revision)` :34。

#### `learning_event`（8 字段）— `V13__learning_loop.sql:36`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `id` | VARCHAR(64) | 否 | — |
| 2 | `user_id` | BIGINT | 否 | — |
| 3 | `event_key` | VARCHAR(150) | 否 | — |
| 4 | `state` | VARCHAR(20) | 否 | — |
| 5 | `attempts` | INT | 否 | 0 |
| 6 | `next_at` | DATETIME | 否 | — |
| 7 | `lease_until` | DATETIME | 是 | NULL |
| 8 | `created_at` | DATETIME | 否 | — |

- 键：`PRIMARY KEY (id)` :37；`UNIQUE (event_key)`（内联，未命名）:37；`INDEX ix_event_due (state, next_at)` :40。

#### `learning_recommendation_settings`（17 字段）— `V13__learning_loop.sql:42`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `user_id` | BIGINT | 否 | — |
| 2 | `revision` | INT | 否 | 0 |
| 3 | `enabled` | INT | 否 | 0 |
| 4 | `preferences_json` | JSON | 否 | — |
| 5 | `pending_reason` | VARCHAR(40) | 是 | NULL |
| 6 | `not_before` | DATETIME | 是 | NULL |
| 7 | `last_task_id` | VARCHAR(64) | 是 | NULL |
| 8 | `last_profile_revision` | INT | 是 | NULL |
| 9 | `last_score` | DOUBLE | 是 | NULL |
| 10 | `last_sufficient` | INT | 否 | 0 |
| 11 | `last_completed_at` | DATETIME | 是 | NULL |
| 12 | `last_release_id` | VARCHAR(64) | 是 | NULL |
| 13 | `last_profile_hash` | VARCHAR(64) | 是 | NULL |
| 14 | `run_token` | VARCHAR(64) | 是 | NULL |
| 15 | `run_until` | DATETIME | 是 | NULL |
| 16 | `pending_task_id` | VARCHAR(64) | 是 | NULL |
| 17 | `attempts` | INT | 否 | 0 |

- 键：`PRIMARY KEY (user_id)` :43。

#### `school_historical_metric`（13 字段）— `V13__learning_loop.sql:50`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `id` | VARCHAR(64) | 否 | — |
| 2 | `program_id` | VARCHAR(100) | 否 | — |
| 3 | `school` | VARCHAR(255) | 否 | — |
| 4 | `college` | VARCHAR(255) | 否 | — |
| 5 | `major_code` | VARCHAR(6) | 否 | — |
| 6 | `metric_year` | INT | 否 | — |
| 7 | `metric_type` | VARCHAR(40) | 否 | — |
| 8 | `exam_subject` | VARCHAR(3) | 是 | NULL |
| 9 | `max_score` | INT | 否 | — |
| 10 | `score` | DOUBLE | 否 | — |
| 11 | `source_json` | JSON | 否 | — |
| 12 | `reviewer_id` | BIGINT | 否 | — |
| 13 | `created_at` | DATETIME | 否 | — |

- 键：`PRIMARY KEY (id)` :51。

### 2.7 V14：招生指标（1 表 + 1 FK + 3 CHECK）

#### `school_admission_metric`（13 字段）— `V14__school_admission_metrics.sql:3`

| # | 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|---|
| 1 | `school_detail_id` | BIGINT UNSIGNED | 否 | — |
| 2 | `metric_type` | VARCHAR(24) | 否 | — |
| 3 | `metric_year` | INT | 是 | NULL |
| 4 | `metric_value` | INT | 是 | NULL |
| 5 | `status` | VARCHAR(24) | 否 | — |
| 6 | `scope_key` | VARCHAR(64) | 否 | — |
| 7 | `scope_label` | VARCHAR(500) | 否 | — |
| 8 | `basis` | VARCHAR(40) | 否 | — |
| 9 | `context_json` | JSON | 否 | — |
| 10 | `sources_json` | JSON | 否 | — |
| 11 | `notice` | VARCHAR(2000) | 否 | — |
| 12 | `content_sha256` | CHAR(64) | 否 | — |
| 13 | `imported_at` | DATETIME | 否 | CURRENT_TIMESTAMP |

- 键：`PRIMARY KEY (school_detail_id, metric_type)` :17。
- 约束原文：

```sql
CONSTRAINT fk_admission_detail FOREIGN KEY (school_detail_id) REFERENCES school_detail(id) ON DELETE CASCADE
CONSTRAINT ck_admission_type CHECK (metric_type IN ('ENROLLMENT','CUTOFF_REFERENCE'))
CONSTRAINT ck_admission_status CHECK (status IN ('OFFICIAL','UNVERIFIED','NOT_PUBLISHED','NOT_FOUND','SCOPE_MISMATCH','CONFLICT'))
CONSTRAINT ck_admission_value CHECK (
  (status IN ('OFFICIAL','UNVERIFIED') AND metric_value IS NOT NULL AND metric_value >= 0 AND metric_year IS NOT NULL)
  OR (status NOT IN ('OFFICIAL','UNVERIFIED') AND metric_value IS NULL)
)
```

- 约束行号：`fk_admission_detail` :18；`ck_admission_type` :19；`ck_admission_status` :20；`ck_admission_value` :21—:24。
- 表选项：`ENGINE=InnoDB DEFAULT CHARSET=utf8mb4` :25；V14 是增量里唯一显式写表选项的文件。

### 2.8 V15 字段变化专项（不遗漏）

- 文件：`V15__profile_degree_type.sql`；目标表 `user`。
- 新增列：`degree_type VARCHAR(16) NULL`，注释 `报考学位类型：academic学硕／professional专硕`，位置 `AFTER exam_year`（:4）。
- 新增约束：`ck_user_degree_type CHECK (degree_type IS NULL OR degree_type IN ('academic','professional'))`（:5）。
- 影响：`user` 从 12 列变为 13 列；该列可空，既有档案保持 NULL（文件头注释 :2）。
- 结论：V15 不是「无结构变化」，字段与 CHECK 都必须出现在摘录和迁移索引里。

### 2.9 增量汇总

| 版本 | 新表 | 新字段 | 改列 | 约束 |
|---|---|---|---|---|
| V7 | 0 | 0 | 1 | 0 |
| V8 | 0 | 0 | 1 | 0 |
| V9 | 0 | 0 | 6 | 0 |
| V10 | 3 | 32 | 0 | 0 |
| V11 | 2 | 14 | 0 | 0 |
| V12 | 2 | 17 | 0 | 0 |
| V13 | 10 | 76 | 0 | 0 |
| V14 | 1 | 13 | 0 | 1 FK + 3 CHECK |
| V15 | 0 | 0 | 1 | 1 CHECK |
| **合计** | **18** | **152** | **9** | **1 FK + 4 CHECK** |

- 新表共 18 张、152 个字段；18 张表都有主键，共 7 个唯一键、7 个普通索引（明细见 2.3—2.7）。
- 约束共 5 个：V14 的 `fk_admission_detail` 与 3 个 CHECK，V15 的 `ck_user_degree_type`。
- 与第 1 节合并：28 张表、264 个字段（103 + 9 + 152）、11 个唯一键、25 个普通索引、1 个外键、4 个 CHECK。

---

本文件两节均已完成：第 1 节 V1 基线、第 2 节 V7—V15 增量。版本与变更定位见 `T10_迁移索引.md`。

