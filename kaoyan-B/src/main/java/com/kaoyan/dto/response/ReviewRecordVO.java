package com.kaoyan.dto.response;

import lombok.Data;

@Data
@lombok.EqualsAndHashCode(callSuper = true)
public class ReviewRecordVO extends QuestionContentVO {
    private String sessionId;
    private Long recordId;
    private Long questionId;
    private Integer orderIndex;
    private String userAnswer;
    private Integer isCorrect;

}
