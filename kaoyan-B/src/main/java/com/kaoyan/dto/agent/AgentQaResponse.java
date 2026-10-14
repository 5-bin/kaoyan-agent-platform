package com.kaoyan.dto.agent;

/**
 * 知识问答响应（FastAPI Agent 返回）
 *
 * @param answer   回答正文
 * @param usage    模型用量/耗时等，可空
 */
public record AgentQaResponse(
        String answer,
        String usage) {
}
