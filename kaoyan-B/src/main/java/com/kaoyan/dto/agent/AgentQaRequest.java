package com.kaoyan.dto.agent;

/**
 * 知识问答请求（发给 FastAPI Agent）
 *
 * @param userId    提问用户 ID
 * @param question  提问内容
 * @param knowledge 知识点（可选）
 */
public record AgentQaRequest(
        Long userId,
        String question,
        String knowledge) {
}
