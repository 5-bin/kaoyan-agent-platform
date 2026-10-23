package com.kaoyan.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
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
               SUM(CASE WHEN grading_status = 'valid' AND is_correct IS NOT NULL THEN 1 ELSE 0 END) AS answered,
               SUM(CASE WHEN grading_status = 'valid' AND is_correct = 1 THEN 1 ELSE 0 END) AS correct,
               MAX(answered_at) AS finishedAt
        FROM practice_record
        WHERE user_id = #{userId}
        GROUP BY session_id
        ORDER BY COALESCE(MAX(answered_at), MAX(created_at)) DESC, session_id DESC
        """)
    Page<SessionSummaryVO> pageSessionSummaries(Page<SessionSummaryVO> page, @Param("userId") Long userId);

}
