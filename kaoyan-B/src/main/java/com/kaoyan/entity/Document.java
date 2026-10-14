package com.kaoyan.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 备考资料（对应 document 表）
 */
@Data
@TableName("document")
public class Document {

    /** 主键 ID */
    @TableId(type = IdType.AUTO)
    private Long id;

    /** 标题 */
    private String title;

    /** 科目 */
    private String subject;

    /** 正文内容 */
    private String content;

    /** 来源 URL */
    private String sourceUrl;

    /** 状态：DRAFT / PENDING_REVIEW / PUBLISHED / REJECTED */
    private String status;

    /** 创建人 ID */
    private Long creatorUserId;

    /** 审核人 ID */
    private Long reviewerUserId;

    /** 审核时间 */
    private LocalDateTime reviewedAt;

    /** 创建时间 */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    /** 更新时间 */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
