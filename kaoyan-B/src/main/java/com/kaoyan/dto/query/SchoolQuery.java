package com.kaoyan.dto.query;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 院校搜索查询
 */
@Schema(description = "院校搜索查询")
public record SchoolQuery(
        @Schema(description = "省份", example = "北京")
        String province,

        @Schema(description = "层次：985/211/双一流", example = "985")
        String level,

        @Schema(description = "专业名（联表模糊搜索）", example = "计算机")
        String majorName
) {
}
