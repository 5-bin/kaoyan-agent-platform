package com.kaoyan.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Data;

/** Explicit display fields shared by historical review and personal marks. */
@Data
public class QuestionContentVO {
    private String subject;
    private String knowledgePoint;
    private String content;
    private String optionA;
    private String optionB;
    private String optionC;
    private String optionD;
    @JsonInclude(JsonInclude.Include.NON_NULL) private String answer;
    @JsonInclude(JsonInclude.Include.NON_NULL) private String analysis;
    private String difficulty;
    private Integer version;
    private String snapshotStatus;
}
