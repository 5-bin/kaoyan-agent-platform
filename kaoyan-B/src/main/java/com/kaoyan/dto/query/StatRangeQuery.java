package com.kaoyan.dto.query;

import io.swagger.v3.oas.annotations.media.Schema;
import org.springframework.format.annotation.DateTimeFormat;

import java.time.LocalDate;

/**
 * 学习统计区间查询
 */
@Schema(description = "学习统计区间查询")
public record StatRangeQuery(
        @Schema(description = "起始日期", example = "2026-01-01")
        @DateTimeFormat(iso = DateTimeFormat.ISO.DATE)
        LocalDate from,

        @Schema(description = "结束日期", example = "2026-01-31")
        @DateTimeFormat(iso = DateTimeFormat.ISO.DATE)
        LocalDate to
) {
}
