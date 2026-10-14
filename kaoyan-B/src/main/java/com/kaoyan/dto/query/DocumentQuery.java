package com.kaoyan.dto.query;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 已发布资料列表查询
 */
@Schema(description = "资料列表查询")
public record DocumentQuery(
        @Schema(description = "科目", example = "数据结构")
        String subject
) {
}
