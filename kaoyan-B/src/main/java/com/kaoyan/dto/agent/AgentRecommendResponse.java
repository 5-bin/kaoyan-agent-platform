package com.kaoyan.dto.agent;

import java.math.BigDecimal;
import java.util.List;

/**
 * 择校推荐响应（FastAPI Agent 返回）
 *
 * @param schools 推荐院校列表
 */
public record AgentRecommendResponse(
        List<RecommendedSchool> schools) {

    /**
     * 单条推荐
     *
     * @param schoolId   院校 ID（可空）
     * @param schoolName 院校名
     * @param reason     推荐理由
     * @param score      匹配分
     */
    public record RecommendedSchool(
            Long schoolId,
            String schoolName,
            String reason,
            BigDecimal score) {
    }
}
