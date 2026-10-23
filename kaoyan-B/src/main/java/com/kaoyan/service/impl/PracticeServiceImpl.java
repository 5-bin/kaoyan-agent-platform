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
    private final com.kaoyan.mapper.QuestionMapper questionMapper;
    private final UserQuestionMarkService userQuestionMarkService;
    private final StudyStatService studyStatService;

    @Override
    @Transactional
    public String startSession(Long userId, String subject, String difficulty, int count) {
        return startSession(userId, subject, difficulty, count, "NORMAL", null);
    }

    @Override
    @Transactional
    public String startSession(Long userId, String subject, String difficulty, int count, String source, List<Long> questionIds) {
        if (count < 1 || count > 50) throw new ApiException(400, 400, "题目数量须为1至50");
        String mode = source == null ? "NORMAL" : source;
        if (!List.of("NORMAL", "WRONG", "FAVORITE").contains(mode)) throw new ApiException(400, 400, "练习来源无效");
        if (questionIds != null && (questionIds.size() > 50 || questionIds.stream().anyMatch(id -> id == null || id <= 0)))
            throw new ApiException(400, 400, "题目集合无效");
        List<Long> allowed = "WRONG".equals(mode) ? userQuestionMarkService.listWrong(userId).stream().map(com.kaoyan.entity.UserQuestionMark::getQuestionId).toList()
                : "FAVORITE".equals(mode) ? userQuestionMarkService.listFavorite(userId).stream().map(com.kaoyan.entity.UserQuestionMark::getQuestionId).toList() : null;
        List<Question> questions;
        if (questionIds != null && !questionIds.isEmpty()) {
            if (allowed != null && !allowed.containsAll(questionIds)) throw new ApiException(404, 404, "题目不存在");
            questions = questionIds.stream().distinct().map(questionService::getById)
                    .filter(QuestionHistoryView::playable).filter(q -> subject == null || subject.isBlank() || subject.equals(q.getSubject()))
                    .filter(q -> difficulty == null || difficulty.isBlank() || difficulty.equals(q.getDifficulty())).limit(count).toList();
        } else if (allowed != null) {
            questions = allowed.stream().distinct().map(questionService::getById).filter(QuestionHistoryView::playable)
                    .filter(q -> subject == null || subject.isBlank() || subject.equals(q.getSubject()))
                    .filter(q -> difficulty == null || difficulty.isBlank() || difficulty.equals(q.getDifficulty())).limit(count).toList();
        } else questions = questionService.listForPractice(subject, difficulty, null, count);
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
            Map<String, Object> fixed = snapshot(q);
            fixed.put("snapshotAtCreation", true);
            r.setQuestionSnapshot(fixed);
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
        Question q = questionMapper.selectForUpdate(questionId);
        if(q==null) throw new ApiException(404,404,"题目不存在");
        if (!"valid".equals(r.getGradingStatus())) throw new ApiException(409, 409, "该项目已不可作答");
        if (!QuestionHistoryView.playable(q)) throw new ApiException(409, 409, "题目已不可练习");
        // New batches grade their immutable creation snapshot. Legacy unanswered batches retain their old behavior.
        boolean fixed = r.getQuestionSnapshot() != null && Boolean.TRUE.equals(r.getQuestionSnapshot().get("snapshotAtCreation"));
        Question grading = fixed ? questionFromSnapshot(r.getQuestionSnapshot(), questionId) : q;
        String expected = grading.getAnswer() == null ? "" : grading.getAnswer().trim().toUpperCase(java.util.Locale.ROOT);
        if (!"SINGLE_CHOICE".equals(grading.getQuestionType()) || !expected.matches("[A-D]")
                || option(grading, expected) == null || option(grading, expected).isBlank())
            throw new ApiException(409, 409, "题目答案配置不完整，请联系管理员");
        if (option(grading, selected) == null || option(grading, selected).isBlank())
            throw new ApiException(400, 400, "选项不属于该题目");
        boolean correct = expected.equals(selected);
        r.setUserAnswer(selected);
        r.setIsCorrect(correct ? 1 : 0);
        r.setAnsweredAt(LocalDateTime.now(java.time.ZoneId.of("Asia/Shanghai")));
        if (!fixed) r.setQuestionSnapshot(snapshot(grading));
        // An overlapping submission must not overwrite the winner or accumulate twice.
        if (!update(r, new LambdaQueryWrapper<PracticeRecord>().eq(PracticeRecord::getId, r.getId())
                .isNull(PracticeRecord::getIsCorrect).eq(PracticeRecord::getGradingStatus, "valid")))
            throw new ApiException(409, 409, "该题已作答或已不可作答");

        if (!correct) {
            userQuestionMarkService.markWrong(userId, questionId);
        }
        studyStatService.accumulate(userId, 1, correct ? 1 : 0, 0);
        return new AnswerVO(questionId, selected, correct ? 1 : 0, expected, grading.getAnalysis());
    }

    private static Map<String, Object> snapshot(Question q) {
        Map<String, Object> s = new java.util.LinkedHashMap<>();
        s.put("id", q.getId()); s.put("subject", q.getSubject()); s.put("knowledgePoint", q.getKnowledgePoint());
        s.put("content", q.getContent()); s.put("answer", q.getAnswer()); s.put("analysis", q.getAnalysis());
        s.put("version", q.getVersion()); s.put("optionA", q.getOptionA()); s.put("optionB", q.getOptionB());
        s.put("optionC", q.getOptionC()); s.put("optionD", q.getOptionD()); s.put("difficulty", q.getDifficulty());
        s.put("questionType", q.getQuestionType()); return s;
    }
    private static Question questionFromSnapshot(Map<String, Object> s, Long id) {
        if (!(s.get("id") instanceof Number n) || n.longValue() != id || !(s.get("content") instanceof String))
            throw new ApiException(409, 409, "批次题目快照缺失");
        Question q = new Question(); q.setId(id); q.setContent((String)s.get("content"));
        q.setQuestionType((String)s.get("questionType")); q.setAnswer((String)s.get("answer")); q.setAnalysis((String)s.get("analysis"));
        q.setOptionA((String)s.get("optionA")); q.setOptionB((String)s.get("optionB"));
        q.setOptionC((String)s.get("optionC")); q.setOptionD((String)s.get("optionD")); return q;
    }

    private static String option(Question q, String key) {
        return switch (key) { case "A" -> q.getOptionA(); case "B" -> q.getOptionB();
            case "C" -> q.getOptionC(); case "D" -> q.getOptionD(); default -> null; };
    }

    @Override
    public Map<String, Object> sessionSummary(Long userId, String sessionId) {
        List<PracticeRecord> records = sessionDetail(userId, sessionId);
        long total = records.size();
        long answered = records.stream().filter(r -> "valid".equals(r.getGradingStatus()) && r.getIsCorrect() != null).count();
        long correct = records.stream().filter(r -> "valid".equals(r.getGradingStatus()) && r.getIsCorrect() != null && r.getIsCorrect() == 1).count();
        Map<String, Object> map = new HashMap<>();
        map.put("sessionId", sessionId);
        map.put("total", total);
        map.put("answered", answered);
        map.put("correct", correct);
        map.put("accuracy", answered == 0 ? 0.0 : (double) correct / answered);
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
