package com.kaoyan.dto.response;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 错题/收藏列表项：mark + question 字段合并
 */
@Data
@lombok.EqualsAndHashCode(callSuper = true)
public class MarkQuestionVO extends QuestionContentVO {
    private Long questionId;
    private Integer wrongCount;
    private LocalDateTime lastWrongAt;
    private LocalDateTime updatedAt;

    private Integer isFavorite;
}
