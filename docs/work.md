> 历史后端生成提示词，不作为当前执行指令。当前接口、配置和运行步骤见根README与docs/rag.md。

---

## 阶段 1：骨架 + 数据库 + Swagger + 通用组件

### 提示词
```
# 任务
创建 Spring Boot 3 单模块项目骨架，生成数据库脚本、种子数据、Swagger 配置、
通用组件（common 包）。

# 上下文
项目根目录：kaoyan-backend
已有 AGENTS.md（见项目根目录），所有规范以 AGENTS.md 为准。

# 需要生成的文件

## 1. pom.xml
- parent: spring-boot-starter-parent 3.5.x
- JDK 17
- 依赖：spring-boot-starter-web、spring-boot-starter-validation、
  spring-boot-starter-security、spring-boot-starter-data-redis、
  mybatis-plus-spring-boot3-starter 3.5.7、mysql-connector-j、
  jjwt-api / jjwt-impl / jjwt-jackson 0.12.x、
  springdoc-openapi-starter-webmvc-ui 2.6.0、
  aliyun-sdk-oss 3.17.4、lombok

## 2. src/main/resources/application.yml
- datasource 指向 MySQL，从环境变量读账号密码
- mybatis-plus 配置：map-underscore-to-camel-case、分页插件
- redis 配置
- jwt 配置：secret 从环境变量读、access-expire-minutes、refresh-expire-days
- springdoc 配置：
  api-docs.path: /v3/api-docs
  swagger-ui.path: /swagger-ui.html
  swagger-ui.tags-sorter: alpha
  swagger-ui.operations-sorter: alpha
  swagger-ui.persist-authorization: true
- oss 配置：
  oss.endpoint: ${OSS_ENDPOINT}
  oss.access-key-id: ${OSS_ACCESS_KEY_ID}
  oss.access-key-secret: ${OSS_ACCESS_KEY_SECRET}
  oss.bucket-name: ${OSS_BUCKET_NAME}
  oss.url-prefix: ${OSS_URL_PREFIX}
- spring.servlet.multipart.max-file-size: 5MB
- spring.servlet.multipart.max-request-size: 5MB

## 3. src/main/java/com/kaoyan/KaoyanApplication.java
- @SpringBootApplication
- @MapperScan("com.kaoyan.mapper")

## 4. src/main/java/com/kaoyan/config/OpenApiConfig.java
- 内容见下方 # OpenApiConfig

## 5. src/main/java/com/kaoyan/config/MybatisPlusConfig.java
- 注册 MybatisPlusInterceptor + PaginationInnerInterceptor(DbType.MYSQL)

## 6. src/main/java/com/kaoyan/common/ 下 6 个类
- Result.java
- ApiException.java
- ErrorCode.java
- GlobalExceptionHandler.java
- PageResult.java
- MyMetaObjectHandler.java
- 内容见下方 # 通用组件

## 7. src/main/resources/db/V1__init.sql
- 内容见下方 # DDL

## 8. src/main/resources/db/V2__seed.sql
- 内容见下方 # 种子数据

# 约束
- 严格按 AGENTS.md
- pom.xml 不要引入未列出的依赖
- application.yml 不硬编码密钥，用 ${ENV_VAR}
- 先输出文件清单和目录结构，我确认后再逐个生成

# OpenApiConfig

package com.kaoyan.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * OpenAPI / Swagger 配置
 */
@Configuration
public class OpenApiConfig {

    private static final String SECURITY_SCHEME_NAME = "bearerAuth";

    @Bean
    public OpenAPI kaoyanOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("考研 Agent 平台 API")
                        .description("Spring Boot 3 + MyBatis-Plus 后端接口文档")
                        .version("v1.0.0")
                        .contact(new Contact().name("kaoyan-agent")))
                .addSecurityItem(new SecurityRequirement().addList(SECURITY_SCHEME_NAME))
                .components(new Components().addSecuritySchemes(SECURITY_SCHEME_NAME,
                        new SecurityScheme()
                                .name(SECURITY_SCHEME_NAME)
                                .type(SecurityScheme.Type.HTTP)
                                .scheme("bearer")
                                .bearerFormat("JWT")
                                .description("填入登录返回的 accessToken，不用加 Bearer 前缀")));
    }
}

# 通用组件

## Result.java

package com.kaoyan.common;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

/**
 * 统一响应
 */
@Data
@Schema(description = "统一响应")
public class Result<T> {

    /** 状态码，0 表示成功 */
    @Schema(description = "状态码，0 表示成功", example = "0")
    private int code;

    /** 提示信息 */
    @Schema(description = "提示信息", example = "ok")
    private String message;

    /** 响应数据 */
    @Schema(description = "响应数据")
    private T data;

    public static <T> Result<T> ok() {
        return ok(null);
    }

    public static <T> Result<T> ok(T data) {
        Result<T> r = new Result<>();
        r.setCode(0);
        r.setMessage("ok");
        r.setData(data);
        return r;
    }

    public static <T> Result<T> fail(int code, String message) {
        Result<T> r = new Result<>();
        r.setCode(code);
        r.setMessage(message);
        return r;
    }
}

## ApiException.java

package com.kaoyan.common;

import lombok.Getter;

/**
 * 业务异常
 */
@Getter
public class ApiException extends RuntimeException {

    /** HTTP 状态码 */
    private final int httpStatus;

    /** 业务错误码 */
    private final int code;

    public ApiException(int httpStatus, int code, String message) {
        super(message);
        this.httpStatus = httpStatus;
        this.code = code;
    }

    public ApiException(int httpStatus, String message) {
        this(httpStatus, httpStatus, message);
    }
}

## ErrorCode.java

package com.kaoyan.common;

/**
 * 错误码
 */
public enum ErrorCode {

    UNAUTHORIZED(401, "未登录"),
    FORBIDDEN(403, "无权访问"),
    NOT_FOUND(404, "资源不存在"),
    CONFLICT(409, "资源冲突"),
    BAD_REQUEST(400, "请求参数错误"),
    INTERNAL_ERROR(500, "服务器内部错误");

    private final int code;
    private final String message;

    ErrorCode(int code, String message) {
        this.code = code;
        this.message = message;
    }

    public int code() { return code; }
    public String message() { return message; }
}

## GlobalExceptionHandler.java

package com.kaoyan.common;

import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.BindException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 全局异常处理
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ApiException.class)
    public ResponseEntity<Result<Void>> handleApi(ApiException e) {
        return ResponseEntity.status(e.getHttpStatus())
                .body(Result.fail(e.getCode(), e.getMessage()));
    }

    @ExceptionHandler({MethodArgumentNotValidException.class, BindException.class})
    public ResponseEntity<Result<Void>> handleValid(BindException e) {
        String msg = e.getBindingResult().getAllErrors().isEmpty()
                ? "参数校验失败"
                : e.getBindingResult().getAllErrors().get(0).getDefaultMessage();
        return ResponseEntity.status(400).body(Result.fail(400, msg));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Result<Void>> handleOther(Exception e, HttpServletRequest req) {
        log.error("未处理异常 uri={}", req.getRequestURI(), e);
        return ResponseEntity.status(500).body(Result.fail(500, "服务器内部错误"));
    }
}

## PageResult.java

package com.kaoyan.common;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;
import java.util.List;

/**
 * 分页响应
 */
@Data
@Schema(description = "分页响应")
public class PageResult<T> {

    /** 总条数 */
    @Schema(description = "总条数", example = "100")
    private long total;

    /** 页码，从 1 开始 */
    @Schema(description = "页码", example = "1")
    private long page;

    /** 每页条数 */
    @Schema(description = "每页条数", example = "10")
    private long size;

    /** 数据列表 */
    @Schema(description = "数据列表")
    private List<T> list;

    public static <T> PageResult<T> of(long total, long page, long size, List<T> list) {
        PageResult<T> r = new PageResult<>();
        r.setTotal(total);
        r.setPage(page);
        r.setSize(size);
        r.setList(list);
        return r;
    }
}

## MyMetaObjectHandler.java

package com.kaoyan.common;

import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import org.apache.ibatis.reflection.MetaObject;
import org.springframework.stereotype.Component;
import java.time.LocalDateTime;

/**
 * MyBatis-Plus 自动填充 createdAt / updatedAt
 */
@Component
public class MyMetaObjectHandler implements MetaObjectHandler {

    @Override
    public void insertFill(MetaObject metaObject) {
        LocalDateTime now = LocalDateTime.now();
        this.strictInsertFill(metaObject, "createdAt", LocalDateTime.class, now);
        this.strictInsertFill(metaObject, "updatedAt", LocalDateTime.class, now);
    }

    @Override
    public void updateFill(MetaObject metaObject) {
        this.strictUpdateFill(metaObject, "updatedAt", LocalDateTime.class, LocalDateTime.now());
    }
}

# DDL

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
  `wrong_count`   INT             NOT NULL DEFAULT 0,
  `last_wrong_at` DATETIME        DEFAULT NULL,
  `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
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

# 种子数据

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
```

---

## 阶段 2：工具类 + OSS 上传 + FileController

### 提示词
```
# 任务
生成工具类、阿里云 OSS 配置和上传工具、文件上传接口。

# 上下文
项目是单模块 Spring Boot 3.5.x，common 包已就绪。
规范以 AGENTS.md 为准。

# 需要生成的文件

## 1. src/main/java/com/kaoyan/config/OssProperties.java
- @ConfigurationProperties(prefix = "oss")
- 字段：endpoint、accessKeyId、accessKeySecret、bucketName、urlPrefix
- 用 @Component 注册

## 2. src/main/java/com/kaoyan/util/OssUtil.java
- 依赖 OssProperties
- 初始化 OSSClient（@PostConstruct 或懒加载）
- 方法：
  - String upload(MultipartFile file, String module)
  - void delete(String objectKey)
  - String buildUrl(String objectKey)
- objectKey 规则：{module}/{yyyyMMdd}/{uuid}.{ext}
- 校验文件类型：jpg/jpeg/png/gif/webp
- 校验大小：<= 5MB
- 抛 ApiException(400, 400, "文件类型不支持" / "文件过大")

## 3. src/main/java/com/kaoyan/util/IdUtil.java
- static String uuid()             // 32 位无横线
- static String shortId()          // 8 位 base62
- static String sessionId()        // UUID 标准格式

## 4. src/main/java/com/kaoyan/util/DateUtil.java
- static String format(LocalDateTime dt)
- static String format(LocalDate d)
- static final String DATE_PATTERN = "yyyy-MM-dd"
- static final String DATETIME_PATTERN = "yyyy-MM-dd HH:mm:ss"

## 5. src/main/java/com/kaoyan/controller/FileController.java
- @Tag(name = "10. 文件", description = "文件上传与删除")
- @RestController @RequestMapping("/api/files") @RequiredArgsConstructor
- POST /upload  multipart/form-data，参数 file、module（可选，默认 common）
  返回 Result<Map<String,String>>，含 url、objectKey
- DELETE /      query 参数 objectKey
  返回 Result<Void>
- 加 @Operation 注解
- 上传头像时前端 module 传 avatar
- currentUserId 用 UserContext.currentUserId() 校验登录

# 约束
- OSS 配置不硬编码，全部从 OssProperties 读
- 上传失败抛 ApiException(500, 500, "上传失败")
- 只允许图片类型，扩展名白名单校验
- 先输出文件清单，我确认后再逐个生成
- 不要动其他 Controller
```

---

## 阶段 3：实体 + Mapper

### 提示词
```
# 任务
按 src/main/resources/db/V1__init.sql 生成 10 个实体类和 10 个 Mapper 接口。

# 上下文
项目是单模块 Spring Boot 3.5.x + MyBatis-Plus 3.5.7。
启动类已加 @MapperScan("com.kaoyan.mapper")。
MyMetaObjectHandler 已就绪。
规范以 AGENTS.md 为准。

# 需要生成的文件

## 实体类（src/main/java/com/kaoyan/entity/）
1. User.java           → user 表
2. Task.java           → task 表
3. Document.java       → document 表
4. School.java         → school 表
5. SchoolDetail.java   → school_detail 表
6. RecommendRecord.java → recommend_record 表
7. Question.java       → question 表
8. PracticeRecord.java → practice_record 表
9. UserQuestionMark.java → user_question_mark 表
10. StudyStat.java     → study_stat 表

## Mapper 接口（src/main/java/com/kaoyan/mapper/）
1. UserMapper
2. TaskMapper
3. DocumentMapper
4. SchoolMapper
5. SchoolDetailMapper
6. RecommendRecordMapper
7. QuestionMapper
8. PracticeRecordMapper
9. UserQuestionMarkMapper
10. StudyStatMapper

# 实体类要求
1. 字段全部 private，@Data 注解
2. 每个字段加中文注释（不是英文）
3. 类上加 Javadoc，写清楚对应哪张表
4. @TableId(type = IdType.AUTO)，Task 用 IdType.ASSIGN_UUID
5. @TableName("`user`") 加反引号，user 是 MySQL 保留字
6. Task 实体加 @TableName(value = "task", autoResultMap = true)
7. Task 的 inputPayload、resultPayload 用 Map<String, Object>，
   加 @TableField(typeHandler = JacksonTypeHandler.class)
8. createdAt 加 @TableField(fill = FieldFill.INSERT)
9. updatedAt 加 @TableField(fill = FieldFill.INSERT_UPDATE)
10. 时间字段用 LocalDateTime，StudyStat.statDate 用 LocalDate
11. RecommendRecord.score 用 BigDecimal
12. User 实体在 status 和 targetSchool 之间加 avatarUrl 字段，
    注释"头像 URL"

# Mapper 要求
1. 全部继承 BaseMapper<T>
2. 加 @Mapper 注解
3. SchoolMapper 额外加：
   @Select("SELECT DISTINCT s.* FROM school s " +
           "JOIN school_detail d ON d.school_id = s.id " +
           "WHERE d.major_name LIKE CONCAT('%', #{majorName}, '%')")
   List<School> selectByMajorName(@Param("majorName") String majorName);
4. QuestionMapper 额外加 selectForPractice，动态条件：
   subject、difficulty、knowledgePoint 可空，active=1，review_status='APPROVED'
   用 <script> 标签，LIMIT #{limit}
5. 不要生成 Service 和 Controller

# 约束
- 严格按 AGENTS.md
- 不主动创建其他辅助类
- 先输出文件清单，我确认后再逐个生成
```

---

## 阶段 4：Service 层

### 提示词
```
# 任务
生成 10 个 Service 接口和 10 个实现类。

# 上下文
实体类和 Mapper 已生成完毕。
规范以 AGENTS.md 为准。
基础 CRUD 用 IService / ServiceImpl 继承方法，接口里不重复声明。

# 需要生成的文件

## Service 接口（src/main/java/com/kaoyan/service/）
## Service 实现（src/main/java/com/kaoyan/service/impl/）

# 各 Service 需要声明的方法

## UserService extends IService<User>
- User register(String username, String rawPassword);
- String login(String username, String rawPassword);
- String refresh(String refreshToken);
- void logout(String authorizationHeader);
- void updateProfile(Long userId, String avatarUrl, String targetSchool,
                    String targetMajor, Integer examYear, String background);
- void updateAvatar(Long userId, String avatarUrl);
- User findByUsername(String username);
- void changeStatus(Long userId, Integer status);
- void changeRole(Long userId, String role);

## TaskService extends IService<Task>
- Task submit(Long userId, String taskType, Map<String, Object> input);
- List<Task> history(Long userId, int page, int size);
- Task detail(Long userId, String taskId);

## DocumentService extends IService<Document>
- List<Document> listPublished(String subject);
- Document create(Long creatorUserId, Document doc);
- void update(Long docId, Document doc);
- void delete(Long docId);
- void review(Long docId, Long reviewerUserId, String status, String comment);
- List<Document> listByStatus(String status, int page, int size);

## SchoolService extends IService<School>
- List<School> search(String province, String level, String majorName);
- Map<String, Object> detail(Long schoolId);
- void create(School school);
- void update(School school);
- void delete(Long schoolId);

## SchoolDetailService extends IService<SchoolDetail>
- List<SchoolDetail> listBySchool(Long schoolId);
- List<SchoolDetail> listBySchoolAndYear(Long schoolId, Integer year);
- void batchSave(Long schoolId, List<SchoolDetail> details);
- void deleteBySchool(Long schoolId);

## RecommendService extends IService<RecommendRecord>
- List<RecommendRecord> generate(Long userId);
- List<RecommendRecord> listByUser(Long userId);
- void delete(Long recordId, Long userId);

## QuestionService extends IService<Question>
- List<Question> listForPractice(String subject, String difficulty,
                                String knowledgePoint, int limit);
- Question detail(Long questionId);
- void create(Question question);
- void update(Question question);
- void delete(Long questionId);
- void submitReview(Long questionId, Long reviewerUserId, String status, String comment);
- List<Question> listPendingReview(int page, int size);

## PracticeService extends IService<PracticeRecord>
- String startSession(Long userId, String subject, String difficulty, int count);
- void answer(Long userId, String sessionId, Long questionId, String userAnswer);
- Map<String, Object> sessionSummary(Long userId, String sessionId);
- List<String> listSessions(Long userId);
- List<PracticeRecord> sessionDetail(Long userId, String sessionId);
- void abandonSession(Long userId, String sessionId);

## UserQuestionMarkService extends IService<UserQuestionMark>
- void markWrong(Long userId, Long questionId);
- void toggleFavorite(Long userId, Long questionId, boolean favorite);
- void removeWrong(Long userId, Long questionId);
- List<UserQuestionMark> listWrong(Long userId);
- List<UserQuestionMark> listFavorite(Long userId);
- boolean isFavorite(Long userId, Long questionId);

## StudyStatService extends IService<StudyStat>
- void accumulate(Long userId, int questionCount, int correctCount, int minutes);
- StudyStat today(Long userId);
- List<StudyStat> range(Long userId, LocalDate from, LocalDate to);
- Map<String, Object> overview(Long userId);

# 实现关键要求

## UserServiceImpl
- register：用户名 trim、检查重复、BCrypt 哈希密码、role=STUDENT、status=1
- login：查 user、BCrypt matches、status 校验、调 JwtService.generateAccess
- refresh：调 JwtService.parse 校验 refresh、签发新 access
- logout：从 Authorization 头取 Token，解析 jti，调 JwtService.revoke
- updateAvatar：查 user，setAvatarUrl，updateById；不存在抛 404
- updateProfile：查 user，逐个 set 字段（avatarUrl 为空则不动），updateById
- 重复用户名抛 ApiException(409, 409, "用户名已存在")
- 密码错误抛 ApiException(401, 401, "用户名或密码错误")

## PracticeServiceImpl.answer
- 加 @Transactional
- 查 practice_record（按 userId + sessionId + questionId）
- 已作答抛 ApiException(409, 409, "该题已作答")
- 比对 question.answer，更新 is_correct、user_answer、answered_at
- 答错调 userQuestionMarkService.markWrong(userId, questionId)
- 调 studyStatService.accumulate(userId, 1, correct ? 1 : 0, 0)

## PracticeServiceImpl.startSession
- 生成 UUID 作为 sessionId（用 IdUtil.sessionId()）
- 调 questionMapper.selectForPractice 拿题
- 无题抛 ApiException(404, 404, "没有符合条件的题目")
- saveBatch 预插 practice_record，user_answer 为 null，grading_status = "valid"

## UserQuestionMarkServiceImpl.markWrong
- upsert 逻辑：先查 user_id + question_id
- 不存在：插入，is_wrong=1，is_favorite=0，wrong_count=1，last_wrong_at=now
- 存在：is_wrong=1，wrong_count++，last_wrong_at=now

## UserQuestionMarkServiceImpl.toggleFavorite
- 同样 upsert，只改 is_favorite

## StudyStatServiceImpl.accumulate
- upsert by user_id + stat_date
- 存在则累加，不存在则插入

## 所有带 userId 的方法
- 查数据后在 Service 内校验归属，不匹配抛 ApiException(403, 403, "无权访问")

# 约束
- @Transactional 只加在 Service 实现类的方法上，不加在接口
- 禁止使用 AOP
- 禁止循环内调 Mapper（startSession 预插用 saveBatch）
- 先输出文件清单，我确认后再逐个生成
- 不要动 Controller
```

---

## 阶段 5：JWT + Security

### 提示词
```
# 任务
生成 JWT 认证和 Spring Security 配置。

# 上下文
项目是 Spring Boot 3.5.x，用 jakarta.* 不是 javax.*。
UserService 已存在，login 方法会调 JwtService.generateAccess。
规范以 AGENTS.md 为准。

# 需要生成的文件

## src/main/java/com/kaoyan/security/
1. JwtService.java
2. JwtAuthenticationFilter.java
3. AuthUser.java
4. UserContext.java

## src/main/java/com/kaoyan/config/
5. SecurityConfig.java

# JwtService 要求
- 依赖：JwtProperties（@ConfigurationProperties(prefix = "jwt")）
  包含 secret、accessExpireMinutes、refreshExpireDays、issuer
- 方法：
  - String generateAccess(User user)
  - String generateRefresh(User user)
  - Claims parse(String token)          // 校验签名和过期，失败抛 ApiException(401,401,...)
  - void revoke(String jti, long ttlSeconds)  // 写 Redis
  - boolean isRevoked(String jti)       // 查 Redis
- Payload 结构：
  { sub: userId, username, role, type: "access"|"refresh", iat, exp, jti }
- 签名算法 HS256，密钥从 JwtProperties.secret 读，长度至少 32 字节
- 用 JJWT 0.12.x 新 API：Jwts.builder().subject().claim().signWith().compact()
- Redis key 前缀："jwt:blacklist:"
- 用 StringRedisTemplate，不要用 RedisTemplate<Object,Object>

## JwtAuthenticationFilter 要求
- 继承 OncePerRequestFilter
- 从 Authorization: Bearer xxx 取 Token
- 校验 type == "access"，refresh 不能当 access 用
- 校验 jti 不在黑名单
- 构造 AuthUser principal，放入 SecurityContextHolder
- 异常不抛出，交给 SecurityConfig 的 entry point 处理
- 不拦截 /api/auth/**、/swagger-ui/**、/v3/api-docs/**、/error

## AuthUser 要求
- record 类型：record AuthUser(Long id, String username, String role) {}

## UserContext 要求
- 静态方法：Long currentUserId()、String currentUsername()、String currentRole()
- 从 SecurityContextHolder 取，未登录抛 ApiException(401, 401, "未登录")

## SecurityConfig 要求
- @Configuration @EnableWebSecurity
- SecurityFilterChain Bean：
  - CSRF 禁用
  - Session 策略 STATELESS
  - /api/auth/**、/swagger-ui/**、/swagger-ui.html、/v3/api-docs/**、/error 放行
  - /api/admin/** 需要 ROLE_ADMIN
  - 其余 /api/** 需要认证（包括 /api/files/**、/api/users/**）
  - 加 JwtAuthenticationFilter 在 UsernamePasswordAuthenticationFilter 之前
  - 认证失败返回 JSON 401，不重定向
  - 无权限返回 JSON 403
- BCryptPasswordEncoder Bean
- AuthenticationEntryPoint 和 AccessDeniedHandler 用 Lambda 写 JSON
- 用 Result 包装响应体

## application.yml 补充
jwt:
  secret: ${JWT_SECRET}
  access-expire-minutes: 60
  refresh-expire-days: 14
  issuer: kaoyan-agent

# 约束
- JJWT 0.12.x API，不用已废弃的 setSubject/setExpiration
- 不硬编码密钥，从环境变量读
- 认证失败返回 JSON，不返回 HTML 重定向
- Swagger 相关路径必须放行
- 禁止使用 AOP
- 先输出文件清单，我确认后再逐个生成
```

---

## 阶段 6：Controller + Swagger 注解

### 提示词
```
# 任务
生成所有 Controller，并加 Swagger 注解。

# 上下文
Service 层和 Security 已就绪。
FileController 已在阶段 2 生成（Tag = "10. 文件"）。
规范以 AGENTS.md 为准。
currentUserId 从 UserContext.currentUserId() 取，禁止强转 principal。

# 需要生成的文件（src/main/java/com/kaoyan/controller/）

1. AuthController.java
2. TaskController.java
3. DocumentController.java
4. SchoolController.java
5. RecommendController.java
6. QuestionController.java
7. PracticeController.java
8. MarkController.java
9. StatController.java
10. UserController.java

# 各 Controller 接口

## AuthController → /api/auth（放行，类加 @SecurityRequirements）
- POST /register    body: {username, password}       → Result<User>
- POST /login       body: {username, password}       → Result<Map<String,String>>
- POST /refresh     body: {refreshToken}             → Result<Map<String,String>>
- POST /logout      header: Authorization            → Result<Void>

## TaskController → /api/tasks
- POST /            body: {taskType, input}          → Result<Task>
- GET  /            param: page, size                → Result<PageResult<Task>>
- GET  /{taskId}                                     → Result<Task>

## DocumentController → /api/documents
- GET  /            param: subject                   → Result<List<Document>>
- GET  /admin/list  param: status, page, size        → Result<PageResult<Document>>
- POST /admin       body: Document                   → Result<Document>
- PUT  /admin/{id}  body: Document                   → Result<Void>
- DELETE /admin/{id}                                 → Result<Void>
- POST /admin/{id}/review body: {status, comment}    → Result<Void>

## SchoolController → /api/schools
- GET  /            param: province, level, majorName → Result<List<School>>
- GET  /{schoolId}                                    → Result<Map<String,Object>>

## RecommendController → /api/recommends
- POST /generate                                     → Result<List<RecommendRecord>>
- GET  /                                             → Result<List<RecommendRecord>>
- DELETE /{id}                                       → Result<Void>

## QuestionController → /api/questions
- GET  /practice    param: subject, difficulty, knowledgePoint, limit → Result<List<Question>>
- GET  /{id}                                          → Result<Question>
- GET  /admin/pending param: page, size               → Result<PageResult<Question>>
- POST /admin       body: Question                    → Result<Question>
- PUT  /admin/{id}  body: Question                    → Result<Void>
- DELETE /admin/{id}                                  → Result<Void>
- POST /admin/{id}/review body: {status, comment}     → Result<Void>

## PracticeController → /api/practice
- POST /sessions    body: {subject, difficulty, count} → Result<Map<String,String>>
- POST /sessions/{sessionId}/answer body: {questionId, answer} → Result<Void>
- GET  /sessions/{sessionId}/summary                   → Result<Map<String,Object>>
- GET  /sessions                                       → Result<List<String>>
- GET  /sessions/{sessionId}                           → Result<List<PracticeRecord>>
- DELETE /sessions/{sessionId}                         → Result<Void>

## MarkController → /api/marks
- POST /wrong/{questionId}                            → Result<Void>
- DELETE /wrong/{questionId}                          → Result<Void>
- POST /favorite/{questionId}                         → Result<Void>
- DELETE /favorite/{questionId}                       → Result<Void>
- GET  /wrong                                         → Result<List<UserQuestionMark>>
- GET  /favorite                                      → Result<List<UserQuestionMark>>

## StatController → /api/stats
- GET  /today                                         → Result<StudyStat>
- GET  /range       param: from, to                   → Result<List<StudyStat>>
- GET  /overview                                      → Result<Map<String,Object>>

## UserController → /api/users
- PUT  /avatar     body: {avatarUrl}                  → Result<Void>
- PUT  /profile    body: {avatarUrl, targetSchool, targetMajor, examYear, background} → Result<Void>
- GET  /me                                            → Result<User>

# Controller 通用要求
1. 类加 @RestController @RequestMapping @RequiredArgsConstructor
2. 类加 @Tag，name 用 "NN. 名称"，NN 从 01 到 11：
   01. 认证 / 02. 任务 / 03. 资料 / 04. 院校 / 05. 推荐
   06. 题库 / 07. 刷题 / 08. 错题收藏 / 09. 统计
   10. 文件（已存在）/ 11. 用户
3. 方法加 @Operation(summary = "...", description = "...")
4. AuthController 类加 @SecurityRequirements
5. 方法参数用 @Valid，请求体用 record DTO，不要直接用实体
6. DTO 类加 @Schema，字段加 @Schema(description, example)
7. 返回统一 Result<T>，分页返回 Result<PageResult<T>>
8. currentUserId 用 UserContext.currentUserId()
9. 不写业务逻辑，只做参数校验和 Service 调用
10. 每个方法加 Javadoc

# DTO 要求（src/main/java/com/kaoyan/dto/request/）
- RegisterRequest(username, password)
- LoginRequest(username, password)
- RefreshRequest(refreshToken)
- TaskSubmitRequest(taskType, input)
- AnswerRequest(questionId, answer)
- ReviewRequest(status, comment)
- StartSessionRequest(subject, difficulty, count)
- AvatarRequest(avatarUrl)
- ProfileRequest(avatarUrl, targetSchool, targetMajor, examYear, background)
- 用 record + jakarta.validation 注解 + @Schema

# 参考示例
AuthController 参考：

package com.kaoyan.controller;

import com.kaoyan.common.Result;
import com.kaoyan.dto.request.LoginRequest;
import com.kaoyan.dto.request.RegisterRequest;
import com.kaoyan.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

/**
 * 认证接口
 */
@Tag(name = "01. 认证", description = "注册、登录、刷新、登出")
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
@SecurityRequirements
public class AuthController {

    private final UserService userService;

    /**
     * 注册
     */
    @Operation(summary = "注册", description = "用户名唯一，密码 6-32 位")
    @PostMapping("/register")
    public Result<?> register(@Valid @RequestBody RegisterRequest req) {
        return Result.ok(userService.register(req.username(), req.password()));
    }

    /**
     * 登录
     */
    @Operation(summary = "登录", description = "返回 accessToken 和 refreshToken")
    @PostMapping("/login")
    public Result<Map<String, String>> login(@Valid @RequestBody LoginRequest req) {
        String access = userService.login(req.username(), req.password());
        return Result.ok(Map.of("accessToken", access));
    }

    /**
     * 刷新 Token
     */
    @Operation(summary = "刷新 Token")
    @PostMapping("/refresh")
    public Result<Map<String, String>> refresh(@RequestBody Map<String, String> body) {
        return Result.ok(Map.of("accessToken",
                userService.refresh(body.get("refreshToken"))));
    }

    /**
     * 登出
     */
    @Operation(summary = "登出", description = "把当前 Token 的 jti 写入黑名单")
    @PostMapping("/logout")
    public Result<Void> logout(@RequestHeader("Authorization") String authorization) {
        userService.logout(authorization);
        return Result.ok();
    }
}

UserController 参考：

package com.kaoyan.controller;

import com.kaoyan.common.Result;
import com.kaoyan.dto.request.AvatarRequest;
import com.kaoyan.dto.request.ProfileRequest;
import com.kaoyan.entity.User;
import com.kaoyan.security.UserContext;
import com.kaoyan.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

/**
 * 用户接口
 */
@Tag(name = "11. 用户", description = "头像与档案")
@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    /**
     * 更新头像
     */
    @Operation(summary = "更新头像",
               description = "先调 /api/files/upload 拿 URL，再传到这里")
    @PutMapping("/avatar")
    public Result<Void> updateAvatar(@Valid @RequestBody AvatarRequest req) {
        userService.updateAvatar(UserContext.currentUserId(), req.avatarUrl());
        return Result.ok();
    }

    /**
     * 更新档案
     */
    @Operation(summary = "更新档案")
    @PutMapping("/profile")
    public Result<Void> updateProfile(@Valid @RequestBody ProfileRequest req) {
        userService.updateProfile(UserContext.currentUserId(),
                req.avatarUrl(), req.targetSchool(), req.targetMajor(),
                req.examYear(), req.background());
        return Result.ok();
    }

    /**
     * 当前用户信息
     */
    @Operation(summary = "当前用户信息")
    @GetMapping("/me")
    public Result<User> me() {
        return Result.ok(userService.getById(UserContext.currentUserId()));
    }
}

# 约束
- 禁止在 Controller 直接调 Mapper
- 禁止强转 principal，用 UserContext
- 禁止使用 AOP
- 先只生成 AuthController + UserController + DTO，我确认后再生成其余
- 分文件输出，标注完整路径
```

---

## 附：Codex 出错回滚策略

| 症状 | 处理 |
|---|---|
| 生成了多余的辅助类 | `git clean -fd` 删掉，重新给更严格的提示词 |
| 改了不该改的文件 | `git checkout -- <file>` 恢复，重来 |
| 编译报 javax 相关错 | 提示词强调 `jakarta.*`，让它重写 |
| N+1 查询 | 贴出问题代码，让它改成单条 SQL JOIN |
| 强转 principal | 提示词里再强调一次用 `UserContext` |
| Swagger UI 404 | 检查 springdoc 是否 2.6.0，Spring Boot 3 不能用 1.x |
| Swagger 里 Token 填了还 401 | 别加 `Bearer ` 前缀，springdoc 自动拼 |
| Swagger 相关路径被拦截 | SecurityConfig 里放行 `/swagger-ui/**`、`/v3/api-docs/**` |
| OSS 上传失败 | 检查环境变量 OSS_ENDPOINT、OSS_ACCESS_KEY_ID、OSS_ACCESS_KEY_SECRET、OSS_BUCKET_NAME 是否设置 |
| 时间字段没填 | 检查实体是否加 @TableField(fill=...)，MyMetaObjectHandler 是否注册 |
| 头像更新后不生效 | 检查 UserController 是否调用 UserContext.currentUserId()，User 实体是否有 avatarUrl |



```
# 上下文
项目是单模块 Spring Boot 3.5.x + MyBatis-Plus 3.5.7 + MySQL 8 + SpringDoc 2.6.0 + OSS 3.17.4，
已存在实体、Mapper、Service、Result、ApiException、UserContext、OssUtil。
用户头像存在 user.avatar_url，不单独建表。

# 约束
- JDK 17，jakarta.* 不是 javax.*
- 外键 user_id，逻辑外键
- 禁止使用 AOP
- 禁止循环内调 Mapper
- 禁止硬编码密钥
- currentUserId 用 UserContext，禁止强转
- Controller 加 @Tag + @Operation，DTO 加 @Schema

# 输出规范
1. 先输出方案和文件清单，我确认后再写代码
2. 代码完整，含包名和导入
3. 多文件分文件输出，标注完整路径
```
