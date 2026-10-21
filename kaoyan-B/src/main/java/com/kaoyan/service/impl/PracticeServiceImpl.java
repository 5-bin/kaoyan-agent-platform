package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.common.ApiException;
import com.kaoyan.common.PageResult;
import com.kaoyan.dto.response.ReviewRecordVO;
import com.kaoyan.dto.response.AnswerVO;
import com.kaoyan.service.QuestionHistoryView;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
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
    public AnswerVO answer(Long userId, String sessionId, Long questionId, String userAnswer) {
        String selected = userAnswer == null ? "" : userAnswer.trim().toUpperCase(java.util.Locale.ROOT);
        if (!selected.matches("[A-D]")) throw new ApiException(400, 400, "请选择有效的单选选项A至D");
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
        if (!"valid".equals(r.getGradingStatus())) throw new ApiException(409, 409, "该项目已不可作答");
        if (!QuestionHistoryView.playable(q)) throw new ApiException(409, 409, "题目已不可练习");
        String expected = q.getAnswer() == null ? "" : q.getAnswer().trim().toUpperCase(java.util.Locale.ROOT);
        if (!"SINGLE_CHOICE".equals(q.getQuestionType()) || !expected.matches("[A-D]")
                || option(q, expected) == null || option(q, expected).isBlank())
            throw new ApiException(409, 409, "题目答案配置不完整，请联系管理员");
        if (option(q, selected) == null || option(q, selected).isBlank())
            throw new ApiException(400, 400, "选项不属于该题目");
        boolean correct = expected.equals(selected);
        r.setUserAnswer(selected);
        r.setIsCorrect(correct ? 1 : 0);
        r.setAnsweredAt(LocalDateTime.now());
        Map<String, Object> snapshot = new java.util.LinkedHashMap<>();
        snapshot.put("id", q.getId()); snapshot.put("subject", q.getSubject());
        snapshot.put("knowledgePoint", q.getKnowledgePoint()); snapshot.put("content", q.getContent());
        snapshot.put("answer", expected); snapshot.put("analysis", q.getAnalysis());
        snapshot.put("version", q.getVersion());
        snapshot.put("optionA", q.getOptionA()); snapshot.put("optionB", q.getOptionB());
        snapshot.put("optionC", q.getOptionC()); snapshot.put("optionD", q.getOptionD());
        snapshot.put("difficulty", q.getDifficulty());
        r.setQuestionSnapshot(snapshot);
        // An overlapping submission must not overwrite the winner or accumulate twice.
        if (!update(r, new LambdaQueryWrapper<PracticeRecord>().eq(PracticeRecord::getId, r.getId())
                .isNull(PracticeRecord::getIsCorrect).eq(PracticeRecord::getGradingStatus, "valid")))
            throw new ApiException(409, 409, "该题已作答或已不可作答");

        if (!correct) {
            userQuestionMarkService.markWrong(userId, questionId);
        }
        studyStatService.accumulate(userId, 1, correct ? 1 : 0, 0);
        return new AnswerVO(questionId, selected, correct ? 1 : 0, expected, q.getAnalysis());
    }

    private static String option(Question q, String key) {
        return switch (key) { case "A" -> q.getOptionA(); case "B" -> q.getOptionB();
            case "C" -> q.getOptionC(); case "D" -> q.getOptionD(); default -> null; };
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
        Page<PracticeRecord> result = lambdaQuery().eq(PracticeRecord::getUserId, userId)
                .eq(PracticeRecord::getSessionId, sessionId).orderByAsc(PracticeRecord::getOrderIndex)
                .page(Page.of(Math.max(page, 1), Math.min(Math.max(size, 1), 50)));
        if (result.getTotal() == 0) {
            throw new ApiException(404, 404, "批次不存在");
        }
        List<ReviewRecordVO> views = result.getRecords().stream().map(r -> {
            ReviewRecordVO view = new ReviewRecordVO();
            view.setSessionId(r.getSessionId()); view.setQuestionId(r.getQuestionId()); view.setOrderIndex(r.getOrderIndex());
            view.setUserAnswer(r.getUserAnswer()); view.setIsCorrect(r.getIsCorrect());
            QuestionHistoryView.populate(view, r, r.getIsCorrect() == null ? questionService.getById(r.getQuestionId()) : null);
            return view;
        }).toList();
        return PageResult.of(result.getTotal(), result.getCurrent(), result.getSize(), views);
    }
}
