package com.kaoyan.dto.response;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 错题/收藏列表项：mark + question 字段合并
 */
@Data
public class MarkQuestionVO {
    private Long questionId;
    private Integer wrongCount;
    private LocalDateTime lastWrongAt;
    private LocalDateTime updatedAt;

    private String subject;
    private String knowledgePoint;
    private String content;
    private String optionA;
    private String optionB;
    private String optionC;
    private String optionD;
    private String answer;
    private String analysis;
    private String difficulty;
    private Integer isFavorite;
}
