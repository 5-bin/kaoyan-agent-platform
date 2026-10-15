package com.kaoyan.dto.agent;

import lombok.Data;

import java.util.List;
import java.util.Map;

/**
 * 与 FastAPI /internal/rag/chat 对齐的统一请求体。
 */
@Data
public class AgentRequest {
    private String taskId;
    private Long userId;
    /** KNOWLEDGE_QA / SCHOOL_RECOMMEND / PRACTICE_SUMMARY / CHAT */
    private String taskType;
    private String userInput;
    private String sessionId;
    /** Server-authorized and already graded snapshots, never client supplied IDs. */
    private List<Map<String, Object>> questions;
    private Map<String, Object> preferences;
    private List<Object> messages;
    private Map<String, Object> profile;
}
