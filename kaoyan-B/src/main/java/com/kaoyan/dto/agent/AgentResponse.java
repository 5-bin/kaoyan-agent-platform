package com.kaoyan.dto.agent;

import lombok.Data;

import java.util.List;

/**
 * FastAPI /internal/rag/chat 统一响应。
 */
@Data
public class AgentResponse {
    private String taskId;
    /** SUCCESS / FAILED */
    private String status;
    private Object result;
    private List<Object> references;
    private String releaseId;
    private String errorMessage;
}
