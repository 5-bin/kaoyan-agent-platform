package com.kaoyan.dto.request;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 更新档案请求
 */
@Schema(description = "更新档案请求")
public record ProfileRequest(
        @Schema(description = "头像 URL（空则不动）")
        String avatarUrl,

        @Schema(description = "目标院校", example = "清华大学")
        String targetSchool,

        @Schema(description = "目标专业", example = "计算机科学与技术")
        String targetMajor,

        @Schema(description = "考试年份", example = "2026")
        Integer examYear,

        @Schema(description = "考生背景")
        String background
) {
}
