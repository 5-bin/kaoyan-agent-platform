package com.kaoyan.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.kaoyan.entity.StudyStat;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/**
 * 学习统计 Service
 */
public interface StudyStatService extends IService<StudyStat> {

    /**
     * 累加今日统计（upsert）
     *
     * @param userId        用户 ID
     * @param questionCount  做题数
     * @param correctCount   正确数
     * @param minutes        学习分钟数
     */
    void accumulate(Long userId, int questionCount, int correctCount, int minutes);

    /**
     * 今日统计
     *
     * @param userId 用户 ID
     * @return 今日统计
     */
    StudyStat today(Long userId);

    /**
     * 区间统计
     *
     * @param userId 用户 ID
     * @param from   起始日期
     * @param to     结束日期
     * @return 统计列表
     */
    List<StudyStat> range(Long userId, LocalDate from, LocalDate to);

    /**
     * 总览
     *
     * @param userId 用户 ID
     * @return 总览
     */
    Map<String, Object> overview(Long userId);
}
