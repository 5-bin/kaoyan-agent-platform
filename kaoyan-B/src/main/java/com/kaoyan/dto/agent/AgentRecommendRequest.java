package com.kaoyan.dto.agent;

import java.util.List;

/**
 * 择校推荐请求（发给 FastAPI Agent）
 *
 * @param userId   用户 ID
 * @param score    预估分数
 * @param major    报考专业
 * @param province 意向省份（可空）
 */
public record AgentRecommendRequest(
        Long userId,
        Integer score,
        String major,
        String province) {
}
