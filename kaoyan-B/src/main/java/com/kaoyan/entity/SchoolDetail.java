package com.kaoyan.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 院校专业与分数线详情（对应 school_detail 表）
 */
@Data
@TableName("school_detail")
public class SchoolDetail {

    /** 主键 ID */
    @TableId(type = IdType.AUTO)
    private Long id;

    /** 院校 ID */
    private Long schoolId;

    /** 专业名 */
    private String majorName;

    /** 专业代码 */
    private String majorCode;

    /** 招生年份 */
    private Integer year;

    /** 招生人数 */
    private Integer enrollmentCount;

    /** 复试分数线 */
    private Integer scoreLine;

    /** 备注 */
    private String remark;

    /** 创建时间 */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    /** 更新时间 */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
