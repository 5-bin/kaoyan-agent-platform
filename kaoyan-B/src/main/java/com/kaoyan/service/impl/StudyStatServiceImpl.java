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
public class StudyStatServiceImpl extends ServiceImpl<StudyStatMapper, StudyStat>
        implements StudyStatService {

    @Override
    @Transactional
    public void accumulate(Long userId, int questionCount, int correctCount, int minutes) {
        LocalDate today = LocalDate.now();
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

    @Override
    public StudyStat today(Long userId) {
        StudyStat s = lambdaQuery()
                .eq(StudyStat::getUserId, userId)
                .eq(StudyStat::getStatDate, LocalDate.now())
                .one();
        if (s == null) {
            s = new StudyStat();
            s.setUserId(userId);
            s.setStatDate(LocalDate.now());
            s.setQuestionCount(0);
            s.setCorrectCount(0);
            s.setStudyMinutes(0);
        }
        return s;
    }

    @Override
    public List<StudyStat> range(Long userId, LocalDate from, LocalDate to) {
        return lambdaQuery()
                .eq(StudyStat::getUserId, userId)
                .ge(from != null, StudyStat::getStatDate, from)
                .le(to != null, StudyStat::getStatDate, to)
                .orderByAsc(StudyStat::getStatDate)
                .list();
    }

    @Override
    public Map<String, Object> overview(Long userId) {
        List<StudyStat> all = lambdaQuery().eq(StudyStat::getUserId, userId).list();
        int q = all.stream().mapToInt(s -> s.getQuestionCount() == null ? 0 : s.getQuestionCount()).sum();
        int c = all.stream().mapToInt(s -> s.getCorrectCount() == null ? 0 : s.getCorrectCount()).sum();
        int m = all.stream().mapToInt(s -> s.getStudyMinutes() == null ? 0 : s.getStudyMinutes()).sum();
        Map<String, Object> map = new HashMap<>();
        map.put("totalQuestions", q);
        map.put("totalCorrect", c);
        map.put("totalMinutes", m);
        map.put("days", all.size());
        map.put("accuracy", q == 0 ? 0.0 : (double) c / q);
        return map;
    }
}
