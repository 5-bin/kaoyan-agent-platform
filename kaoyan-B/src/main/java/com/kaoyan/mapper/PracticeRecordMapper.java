package com.kaoyan.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.kaoyan.dto.response.ReviewRecordVO;
import com.kaoyan.dto.response.SessionSummaryVO;
import com.kaoyan.entity.PracticeRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface PracticeRecordMapper extends BaseMapper<PracticeRecord> {

    @Select("""
        SELECT session_id AS sessionId,
               COUNT(*) AS total,
               SUM(CASE WHEN is_correct IS NOT NULL THEN 1 ELSE 0 END) AS answered,
               SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct,
               MAX(answered_at) AS finishedAt
        FROM practice_record
        WHERE user_id = #{userId}
        GROUP BY session_id
        HAVING MAX(answered_at) IS NOT NULL
        ORDER BY finishedAt DESC, session_id DESC
        """)
    Page<SessionSummaryVO> pageSessionSummaries(Page<SessionSummaryVO> page, @Param("userId") Long userId);

    @Select("""
        SELECT r.session_id AS sessionId,
               r.question_id AS questionId,
               r.order_index AS orderIndex,
               r.user_answer AS userAnswer,
               r.is_correct AS isCorrect,
               q.subject AS subject,
               q.knowledge_point AS knowledgePoint,
               q.content AS content,
               q.option_a AS optionA,
               q.option_b AS optionB,
               q.option_c AS optionC,
               q.option_d AS optionD,
               q.answer AS answer,
               q.analysis AS analysis,
               q.difficulty AS difficulty
        FROM practice_record r
        LEFT JOIN question q ON q.id = r.question_id
        WHERE r.user_id = #{userId} AND r.session_id = #{sessionId}
        ORDER BY r.order_index ASC
        """)
    Page<ReviewRecordVO> pageReview(Page<ReviewRecordVO> page,
                                    @Param("userId") Long userId,
                                    @Param("sessionId") String sessionId);
}
