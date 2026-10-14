package com.kaoyan.dto.response;

import lombok.Data;

@Data
public class ReviewRecordVO {
    private String sessionId;
    private Long questionId;
    private Integer orderIndex;
    private String userAnswer;
    private Integer isCorrect;

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
}
