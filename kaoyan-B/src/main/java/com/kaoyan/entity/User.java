package com.kaoyan.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 用户账号与档案（对应 user 表）
 */
@Data
@TableName("`user`")
public class User {

    /** 主键 ID */
    @TableId(type = IdType.AUTO)
    private Long id;

    /** 用户名（唯一） */
    private String username;

    /** BCrypt 密码哈希 */
    @com.fasterxml.jackson.annotation.JsonIgnore
    private String passwordHash;

    /** 角色：STUDENT / ADMIN */
    private String role;

    /** 状态：1 正常 0 禁用 */
    private Integer status;

    /** 头像 URL */
    private String avatarUrl;

    /** 目标院校 */
    private String targetSchool;

    /** 目标专业 */
    private String targetMajor;

    /** 考试年份 */
    private Integer examYear;

    /** 考生背景 */
    private String background;

    /** 创建时间 */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    /** 更新时间 */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
