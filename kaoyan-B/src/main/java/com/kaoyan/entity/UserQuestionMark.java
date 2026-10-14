package com.kaoyan.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 错题与收藏（对应 user_question_mark 表）
 */
@Data
@TableName("user_question_mark")
public class UserQuestionMark {

    /** 主键 ID */
    @TableId(type = IdType.AUTO)
    private Long id;

    /** 用户 ID */
    private Long userId;

    /** 题目 ID */
    private Long questionId;

    /** 是否收藏：1 是 0 否 */
    private Integer isFavorite;

    /** 是否错题：1 是 0 否 */
    private Integer isWrong;

    /** 错误次数 */
    private Integer wrongCount;

    /** 最近一次做错时间 */
    private LocalDateTime lastWrongAt;

    /** 创建时间 */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    /** 更新时间 */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
