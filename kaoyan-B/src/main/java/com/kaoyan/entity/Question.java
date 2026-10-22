package com.kaoyan.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 题库（对应 question 表）
 */
@Data
@TableName("question")
public class Question {

    /** 主键 ID */
    @TableId(type = IdType.AUTO)
    private Long id;

    /** 科目 */
    private String subject;

    /** 知识点 */
    private String knowledgePoint;

    /** 题干 */
    private String content;

    /** 选项 A */
    private String optionA;

    /** 选项 B */
    private String optionB;

    /** 选项 C */
    private String optionC;

    /** 选项 D */
    private String optionD;

    /** 正确答案 */
    private String answer;

    /** 解析 */
    private String analysis;

    /** 难度：EASY / MEDIUM / HARD */
    private String difficulty;

    /** 题型 */
    private String questionType;

    /** V9 source metadata; null on legacy questions with undocumented provenance. */
    private String sourceType;
    private String sourceName;
    private String sourceLocator;
    private Integer sourceYear;
    private String sourceQuestionNo;
    private String permissionNote;

    /** 版本号 */
    private Integer version;

    /** 是否启用：1 启用 0 停用 */
    private Integer active;

    /** 稳定排序值 */
    private Integer stableOrder;

    /** 审核状态：PENDING_REVIEW / APPROVED / REJECTED */
    private String reviewStatus;

    /** 审核人 ID */
    private Long reviewerUserId;

    /** 审核时间 */
    private LocalDateTime reviewedAt;

    /** 审核意见 */
    private String reviewComment;

    /** 创建时间 */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    /** 更新时间 */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
