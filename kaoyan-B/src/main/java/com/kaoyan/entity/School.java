package com.kaoyan.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 院校基础信息（对应 school 表）
 */
@Data
@TableName("school")
public class School {

    /** 主键 ID */
    @TableId(type = IdType.AUTO)
    private Long id;

    /** 院校名称 */
    private String name;

    /** 所在省份 */
    private String province;

    /** 层次：985 / 211 / 双一流 */
    private String level;

    /** 创建时间 */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    /** 更新时间 */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
