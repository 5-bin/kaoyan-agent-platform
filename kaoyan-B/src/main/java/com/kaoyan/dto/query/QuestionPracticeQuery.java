package com.kaoyan.dto.query;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 刷题抽题查询
 */
@Schema(description = "刷题抽题查询")
public record QuestionPracticeQuery(
        @Schema(description = "科目", example = "数据结构")
        String subject,

        @Schema(description = "难度：EASY/MEDIUM/HARD", example = "EASY")
        String difficulty,

        @Schema(description = "知识点", example = "线性表")
        String knowledgePoint,

        @Schema(description = "抽取数量", example = "5")
        Integer limit
) {

    /**
     * 有效抽取数量（默认 1，上限 100）
     *
     * @return 数量
     */
    public int effectiveLimit() {
        if (limit == null || limit < 1) {
            return 1;
        }
        return Math.min(limit, 100);
    }
}
