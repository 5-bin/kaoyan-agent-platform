package com.kaoyan.dto.response;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class SessionSummaryVO {
    private String sessionId;
    private Integer total;
    private Integer answered;
    private Integer correct;
    private Integer accuracy;
    private LocalDateTime finishedAt;
}
