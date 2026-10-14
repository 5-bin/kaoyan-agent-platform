package com.kaoyan.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 刷题记录（对应 practice_record 表）
 */
@Data
@TableName("practice_record")
public class PracticeRecord {

    /** 主键 ID */
    @TableId(type = IdType.AUTO)
    private Long id;

    /** 用户 ID */
    private Long userId;

    /** 一次刷题批次 */
    private String sessionId;

    /** 题目 ID */
    private Long questionId;

    /** 批次内顺序 */
    private Integer orderIndex;

    /** 用户作答 */
    private String userAnswer;

    /** 是否正确：1 正确 0 错误 */
    private Integer isCorrect;

    /** 批改状态 */
    private String gradingStatus;

    /** 作答时间 */
    private LocalDateTime answeredAt;

    /** 创建时间 */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
