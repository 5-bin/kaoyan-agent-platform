package com.kaoyan.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * Agent 任务（对应 task 表）
 */
@Data
@TableName(value = "task", autoResultMap = true)
public class Task {

    /** 任务 ID（UUID） */
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    /** 所属用户 ID */
    private Long userId;

    /** 任务类型：KNOWLEDGE_QA / SCHOOL_RECOMMEND */
    private String taskType;

    /** 状态：RUNNING / SUCCESS / FAILED / CANCELLED；兼容旧PENDING记录。 */
    private String status;

    /** 请求参数 */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> inputPayload;

    /** Agent 返回结果 */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> resultPayload;

    /** 版本标识 */
    private String releaseId;

    /** 失败原因 */
    private String errorMessage;

    /** Display deletion only; quota queries intentionally retain these rows. */
    @com.fasterxml.jackson.annotation.JsonIgnore
    private LocalDateTime deletedAt;

    /** 创建时间 */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    /** 更新时间 */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
