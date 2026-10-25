package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.entity.StudyStat;
import com.kaoyan.mapper.StudyStatMapper;
import com.kaoyan.service.StudyStatService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 学习统计 Service 实现
 */
@Service
@lombok.RequiredArgsConstructor
public class StudyStatServiceImpl extends ServiceImpl<StudyStatMapper, StudyStat>
        implements StudyStatService {

    private final com.kaoyan.mapper.PracticeRecordMapper attempts;
    private final com.kaoyan.mapper.UserQuestionMarkMapper marks;
    private final com.kaoyan.mapper.QuestionMapper questions;
    private static final java.time.ZoneId SHANGHAI = java.time.ZoneId.of("Asia/Shanghai");

    @Override
    @Transactional
    public void accumulate(Long userId, int questionCount, int correctCount, int minutes) {
        LocalDate today = LocalDate.now(SHANGHAI);
        StudyStat s = lambdaQuery()
                .eq(StudyStat::getUserId, userId)
                .eq(StudyStat::getStatDate, today)
                .one();
        if (s == null) {
            s = new StudyStat();
            s.setUserId(userId);
            s.setStatDate(today);
            s.setQuestionCount(questionCount);
            s.setCorrectCount(correctCount);
            s.setStudyMinutes(minutes);
            save(s);
        } else {
            s.setQuestionCount(s.getQuestionCount() + questionCount);
            s.setCorrectCount(s.getCorrectCount() + correctCount);
            s.setStudyMinutes(s.getStudyMinutes() + minutes);
            updateById(s);
        }
    }

    private List<com.kaoyan.entity.PracticeRecord> valid(Long userId) {
        return attempts.selectList(new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<com.kaoyan.entity.PracticeRecord>()
                .eq(com.kaoyan.entity.PracticeRecord::getUserId, userId)
                .eq(com.kaoyan.entity.PracticeRecord::getGradingStatus, "valid")
                .isNotNull(com.kaoyan.entity.PracticeRecord::getIsCorrect)
                .isNotNull(com.kaoyan.entity.PracticeRecord::getAnsweredAt));
    }
    private StudyStat stat(Long userId, LocalDate day, List<com.kaoyan.entity.PracticeRecord> records) {
        StudyStat s = new StudyStat(); s.setUserId(userId); s.setStatDate(day);
        s.setQuestionCount(records.size()); s.setCorrectCount((int)records.stream().filter(r -> Integer.valueOf(1).equals(r.getIsCorrect())).count());
        s.setStudyMinutes(null); return s;
    }
    @Override public StudyStat today(Long userId) {
        LocalDate day = LocalDate.now(SHANGHAI);
        return stat(userId, day, valid(userId).stream().filter(r -> day.equals(r.getAnsweredAt().toLocalDate())).toList());
    }
    @Override public List<StudyStat> range(Long userId, LocalDate from, LocalDate to) {
        LocalDate end = to == null ? LocalDate.now(SHANGHAI) : to;
        LocalDate start = from == null ? end.minusDays(29) : from;
        validateRange(start, end);
        var grouped = valid(userId).stream().filter(r -> !r.getAnsweredAt().toLocalDate().isBefore(start) && !r.getAnsweredAt().toLocalDate().isAfter(end))
                .collect(java.util.stream.Collectors.groupingBy(r -> r.getAnsweredAt().toLocalDate(), java.util.TreeMap::new, java.util.stream.Collectors.toList()));
        return grouped.entrySet().stream().map(e -> stat(userId,e.getKey(),e.getValue())).toList();
    }
    @Override public Map<String,Object> overview(Long userId) {
        var rows = valid(userId); var s = stat(userId,null,rows); Map<String,Object> result = new java.util.LinkedHashMap<>();
        result.put("totalQuestions",s.getQuestionCount()); result.put("totalCorrect",s.getCorrectCount()); result.put("totalMinutes",null);
        result.put("days",rows.stream().map(r -> r.getAnsweredAt().toLocalDate()).distinct().count());
        result.put("accuracy",rows.isEmpty() ? 0.0 : (double)s.getCorrectCount()/rows.size()); return result;
    }
    private void validateRange(LocalDate from, LocalDate to) {
        if (from.isAfter(to) || java.time.temporal.ChronoUnit.DAYS.between(from,to) > 3660)
            throw new com.kaoyan.common.ApiException(400,400,"日期范围无效（最多3660天）");
    }
    @Override public Map<String,Object> learning(Long userId, LocalDate from, LocalDate to, String subject) {
        LocalDate end = to == null ? LocalDate.now(SHANGHAI) : to, start = from == null ? end.minusDays(29) : from;
        validateRange(start,end);
        var rows = valid(userId).stream().filter(r -> !r.getAnsweredAt().toLocalDate().isBefore(start) && !r.getAnsweredAt().toLocalDate().isAfter(end))
                .filter(r -> subject == null || subject.isBlank() || (r.getQuestionSnapshot() != null && subject.equals(r.getQuestionSnapshot().get("subject")))).toList();
        Map<String,Object> result = new java.util.LinkedHashMap<>();
        int correct = (int)rows.stream().filter(r -> Integer.valueOf(1).equals(r.getIsCorrect())).count();
        result.put("questionCount",rows.size()); result.put("correctCount",correct);
        result.put("uniqueQuestions",rows.stream().map(com.kaoyan.entity.PracticeRecord::getQuestionId).distinct().count());
        var marked = marks.selectList(new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<com.kaoyan.entity.UserQuestionMark>()
                .eq(com.kaoyan.entity.UserQuestionMark::getUserId,userId).eq(com.kaoyan.entity.UserQuestionMark::getIsWrong,1));
        // Current marks are independent from historical wrong attempts, and are not filtered by answer date.
        if (subject != null && !subject.isBlank()) {
            var ids = valid(userId).stream().filter(r -> r.getQuestionSnapshot()!=null && subject.equals(r.getQuestionSnapshot().get("subject")))
                    .map(com.kaoyan.entity.PracticeRecord::getQuestionId).collect(java.util.stream.Collectors.toSet());
            marked = marked.stream().filter(m -> ids.contains(m.getQuestionId()) || java.util.Optional.ofNullable(questions.selectById(m.getQuestionId())).map(q -> subject.equals(q.getSubject())).orElse(false)).toList();
        }
        result.put("wrongCount",marked.size()); result.put("accuracy", rows.isEmpty() ? null : (double)correct/rows.size());
        result.put("from",start.toString()); result.put("to",end.toString()); result.put("timezone","Asia/Shanghai");
        result.put("studyMinutes",null); result.put("hintAssisted",null); result.put("independentAnswers",null);
        result.put("unrecorded",List.of("studyMinutes","hintAssisted","independentAnswers"));
        var daily = rows.stream().collect(java.util.stream.Collectors.groupingBy(r -> r.getAnsweredAt().toLocalDate(), java.util.TreeMap::new, java.util.stream.Collectors.toList()));
        result.put("daily",daily.entrySet().stream().map(e -> Map.of("date",e.getKey().toString(),"statDate",e.getKey().toString(),"questionCount",e.getValue().size(),"correctCount",e.getValue().stream().filter(r -> Integer.valueOf(1).equals(r.getIsCorrect())).count())).toList());
        var points = rows.stream().collect(java.util.stream.Collectors.groupingBy(r -> r.getQuestionSnapshot()!=null && r.getQuestionSnapshot().get("knowledgePoint") instanceof String point ? point : "历史知识点未记录",java.util.TreeMap::new,java.util.stream.Collectors.toList()));
        result.put("knowledgePoints",points.entrySet().stream().map(e -> Map.of("knowledgePoint",e.getKey(),"questionCount",e.getValue().size(),"correctCount",e.getValue().stream().filter(r -> Integer.valueOf(1).equals(r.getIsCorrect())).count(),"sampleInsufficient",e.getValue().size()<5)).toList());
        return result;
    }
}
