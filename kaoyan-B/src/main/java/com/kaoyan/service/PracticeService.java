package com.kaoyan.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.kaoyan.common.PageResult;
import com.kaoyan.dto.response.ReviewRecordVO;
import com.kaoyan.dto.response.AnswerVO;
import com.kaoyan.dto.response.SessionSummaryVO;
import com.kaoyan.entity.PracticeRecord;

import java.util.List;
import java.util.Map;

/**
 * 刷题 Service
 */
public interface PracticeService extends IService<PracticeRecord> {

    /**
     * 开始一次刷题批次
     *
     * @param userId     用户 ID
     * @param subject    科目（可空）
     * @param difficulty 难度（可空）
     * @param count      题目数量
     * @return sessionId
     */
    String startSession(Long userId, String subject, String difficulty, int count);
    String startSession(Long userId, String subject, String difficulty, int count, String source, List<Long> questionIds);

    /**
     * 作答一题
     *
     * @param userId     用户 ID
     * @param sessionId  批次 ID
     * @param questionId 题目 ID
     * @param userAnswer 用户答案
     */
    AnswerVO answer(Long userId, String sessionId, Long questionId, String userAnswer);

    /**
     * 批次总结
     *
     * @param userId    用户 ID
     * @param sessionId 批次 ID
     * @return 总结
     */
    Map<String, Object> sessionSummary(Long userId, String sessionId);

    /**
     * 列出用户所有 sessionId
     *
     * @param userId 用户 ID
     * @return sessionId 列表
     */
    List<String> listSessions(Long userId);

    /**
     * 批次详情（逐题作答情况）
     *
     * @param userId    用户 ID
     * @param sessionId 批次 ID
     * @return 作答记录
     */
    List<PracticeRecord> sessionDetail(Long userId, String sessionId);

    /**
     * 放弃一次批次
     *
     * @param userId    用户 ID
     * @param sessionId 批次 ID
     */
    void abandonSession(Long userId, String sessionId);

    /** 分页：我的刷题批次汇总 */
    PageResult<SessionSummaryVO> pageSessions(Long userId, int page, int size);

    /** 分页：某批次的逐题回顾（带题目详情） */
    PageResult<ReviewRecordVO> pageReview(Long userId, String sessionId, int page, int size);
}
