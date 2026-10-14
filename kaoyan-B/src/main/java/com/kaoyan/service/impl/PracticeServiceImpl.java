package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.common.ApiException;
import com.kaoyan.common.PageResult;
import com.kaoyan.dto.response.ReviewRecordVO;
import com.kaoyan.dto.response.SessionSummaryVO;
import com.kaoyan.entity.PracticeRecord;
import com.kaoyan.entity.Question;
import com.kaoyan.mapper.PracticeRecordMapper;
import com.kaoyan.service.PracticeService;
import com.kaoyan.service.QuestionService;
import com.kaoyan.service.StudyStatService;
import com.kaoyan.service.UserQuestionMarkService;
import com.kaoyan.util.IdUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 刷题 Service 实现
 */
@Service
@RequiredArgsConstructor
public class PracticeServiceImpl extends ServiceImpl<PracticeRecordMapper, PracticeRecord>
        implements PracticeService {

    private final QuestionService questionService;
    private final UserQuestionMarkService userQuestionMarkService;
    private final StudyStatService studyStatService;

    @Override
    @Transactional
    public String startSession(Long userId, String subject, String difficulty, int count) {
        List<Question> questions = questionService.listForPractice(subject, difficulty, null, count);
        if (questions.isEmpty()) {
            throw new ApiException(404, 404, "没有符合条件的题目");
        }
        String sessionId = IdUtil.sessionId();
        int order = 0;
        for (Question q : questions) {
            PracticeRecord r = new PracticeRecord();
            r.setUserId(userId);
            r.setSessionId(sessionId);
            r.setQuestionId(q.getId());
            r.setOrderIndex(order++);
            r.setGradingStatus("valid");
            save(r);
        }
        return sessionId;
    }

    @Override
    @Transactional
    public void answer(Long userId, String sessionId, Long questionId, String userAnswer) {
        PracticeRecord r = lambdaQuery()
                .eq(PracticeRecord::getUserId, userId)
                .eq(PracticeRecord::getSessionId, sessionId)
                .eq(PracticeRecord::getQuestionId, questionId)
                .one();
        if (r == null) {
            throw new ApiException(404, 404, "作答记录不存在");
        }
        if (r.getIsCorrect() != null) {
            throw new ApiException(409, 409, "该题已作答");
        }
        Question q = questionService.detail(questionId);
        boolean correct = q.getAnswer() != null && q.getAnswer().equalsIgnoreCase(userAnswer == null ? "" : userAnswer.trim());
        r.setUserAnswer(userAnswer);
        r.setIsCorrect(correct ? 1 : 0);
        r.setAnsweredAt(LocalDateTime.now());
        Map<String, Object> snapshot = new java.util.LinkedHashMap<>();
        snapshot.put("id", q.getId()); snapshot.put("subject", q.getSubject());
        snapshot.put("knowledgePoint", q.getKnowledgePoint()); snapshot.put("content", q.getContent());
        snapshot.put("answer", q.getAnswer()); snapshot.put("analysis", q.getAnalysis());
        snapshot.put("version", q.getVersion());
        r.setQuestionSnapshot(snapshot);
        updateById(r);

        if (!correct) {
            userQuestionMarkService.markWrong(userId, questionId);
        }
        studyStatService.accumulate(userId, 1, correct ? 1 : 0, 0);
    }

    @Override
    public Map<String, Object> sessionSummary(Long userId, String sessionId) {
        List<PracticeRecord> records = sessionDetail(userId, sessionId);
        long total = records.size();
        long answered = records.stream().filter(r -> r.getIsCorrect() != null).count();
        long correct = records.stream().filter(r -> r.getIsCorrect() != null && r.getIsCorrect() == 1).count();
        Map<String, Object> map = new HashMap<>();
        map.put("sessionId", sessionId);
        map.put("total", total);
        map.put("answered", answered);
        map.put("correct", correct);
        map.put("accuracy", total == 0 ? 0.0 : (double) correct / total);
        return map;
    }

    @Override
    public List<String> listSessions(Long userId) {
        return lambdaQuery()
                .select(PracticeRecord::getSessionId)
                .eq(PracticeRecord::getUserId, userId)
                .groupBy(PracticeRecord::getSessionId)
                .orderByDesc(PracticeRecord::getSessionId)
                .list()
                .stream()
                .map(PracticeRecord::getSessionId)
                .distinct()
                .toList();
    }

    @Override
    public List<PracticeRecord> sessionDetail(Long userId, String sessionId) {
        List<PracticeRecord> list = lambdaQuery()
                .eq(PracticeRecord::getUserId, userId)
                .eq(PracticeRecord::getSessionId, sessionId)
                .orderByAsc(PracticeRecord::getOrderIndex)
                .list();
        if (list.isEmpty()) {
            throw new ApiException(404, 404, "批次不存在");
        }
        return list;
    }

    @Override
    @Transactional
    public void abandonSession(Long userId, String sessionId) {
        lambdaUpdate()
                .eq(PracticeRecord::getUserId, userId)
                .eq(PracticeRecord::getSessionId, sessionId)
                .remove();
    }

    @Override
    public PageResult<SessionSummaryVO> pageSessions(Long userId, int page, int size) {
        Page<SessionSummaryVO> p = Page.of(Math.max(page, 1), Math.min(Math.max(size, 1), 50));
        Page<SessionSummaryVO> result = baseMapper.pageSessionSummaries(p, userId);
        result.getRecords().forEach(r -> {
            int ans = r.getAnswered() == null ? 0 : r.getAnswered();
            int cor = r.getCorrect() == null ? 0 : r.getCorrect();
            r.setTotal(r.getTotal() == null ? 0 : r.getTotal());
            r.setAccuracy(ans == 0 ? 0 : (int) Math.round(cor * 100.0 / ans));
        });
        return PageResult.of(result.getTotal(), result.getCurrent(), result.getSize(), result.getRecords());
    }

    @Override
    public PageResult<ReviewRecordVO> pageReview(Long userId, String sessionId, int page, int size) {
        Page<ReviewRecordVO> p = Page.of(Math.max(page, 1), Math.min(Math.max(size, 1), 50));
        Page<ReviewRecordVO> result = baseMapper.pageReview(p, userId, sessionId);
        if (result.getTotal() == 0) {
            throw new ApiException(404, 404, "批次不存在");
        }
        return PageResult.of(result.getTotal(), result.getCurrent(), result.getSize(), result.getRecords());
    }
}
