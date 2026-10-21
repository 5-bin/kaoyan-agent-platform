package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.common.PageResult;
import com.kaoyan.dto.response.MarkQuestionVO;
import com.kaoyan.entity.UserQuestionMark;
import com.kaoyan.entity.PracticeRecord;
import com.kaoyan.mapper.PracticeRecordMapper;
import com.kaoyan.mapper.QuestionMapper;
import com.kaoyan.service.QuestionHistoryView;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import com.kaoyan.mapper.UserQuestionMarkMapper;
import com.kaoyan.service.UserQuestionMarkService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 错题与收藏 Service 实现
 */
@Service
@RequiredArgsConstructor
public class UserQuestionMarkServiceImpl extends ServiceImpl<UserQuestionMarkMapper, UserQuestionMark>
        implements UserQuestionMarkService {

    private final PracticeRecordMapper attempts;
    private final QuestionMapper questions;

    private UserQuestionMark find(Long userId, Long questionId) {
        return lambdaQuery()
                .eq(UserQuestionMark::getUserId, userId)
                .eq(UserQuestionMark::getQuestionId, questionId)
                .one();
    }

    @Override
    @Transactional
    public void markWrong(Long userId, Long questionId) {
        UserQuestionMark m = find(userId, questionId);
        LocalDateTime now = LocalDateTime.now();
        if (m == null) {
            m = new UserQuestionMark();
            m.setUserId(userId);
            m.setQuestionId(questionId);
            m.setIsWrong(1);
            m.setIsFavorite(0);
            m.setWrongCount(1);
            m.setLastWrongAt(now);
            save(m);
        } else {
            m.setIsWrong(1);
            m.setWrongCount(m.getWrongCount() == null ? 1 : m.getWrongCount() + 1);
            m.setLastWrongAt(now);
            updateById(m);
        }
    }

    @Override
    @Transactional
    public void toggleFavorite(Long userId, Long questionId, boolean favorite) {
        UserQuestionMark m = find(userId, questionId);
        if (m == null) {
            m = new UserQuestionMark();
            m.setUserId(userId);
            m.setQuestionId(questionId);
            m.setIsFavorite(favorite ? 1 : 0);
            m.setIsWrong(0);
            m.setWrongCount(0);
            save(m);
        } else {
            m.setIsFavorite(favorite ? 1 : 0);
            updateById(m);
        }
    }

    @Override
    @Transactional
    public void removeWrong(Long userId, Long questionId) {
        UserQuestionMark m = find(userId, questionId);
        if (m != null) {
            m.setIsWrong(0);
            updateById(m);
        }
    }

    @Override
    public List<UserQuestionMark> listWrong(Long userId) {
        return lambdaQuery()
                .eq(UserQuestionMark::getUserId, userId)
                .eq(UserQuestionMark::getIsWrong, 1)
                .orderByDesc(UserQuestionMark::getLastWrongAt)
                .list();
    }

    @Override
    public List<UserQuestionMark> listFavorite(Long userId) {
        return lambdaQuery()
                .eq(UserQuestionMark::getUserId, userId)
                .eq(UserQuestionMark::getIsFavorite, 1)
                .orderByDesc(UserQuestionMark::getUpdatedAt)
                .list();
    }

    @Override
    public boolean isFavorite(Long userId, Long questionId) {
        UserQuestionMark m = find(userId, questionId);
        return m != null && m.getIsFavorite() != null && m.getIsFavorite() == 1;
    }

    @Override
    public PageResult<MarkQuestionVO> pageWrong(Long userId, int page, int size) {
        Page<MarkQuestionVO> p = Page.of(Math.max(page, 1), Math.min(Math.max(size, 1), 50));
        Page<MarkQuestionVO> result = baseMapper.pageWrong(p, userId);
        result.getRecords().forEach(view -> history(userId, view));
        return PageResult.of(result.getTotal(), result.getCurrent(), result.getSize(), result.getRecords());
    }

    @Override
    public PageResult<MarkQuestionVO> pageFavorite(Long userId, int page, int size) {
        Page<MarkQuestionVO> p = Page.of(Math.max(page, 1), Math.min(Math.max(size, 1), 50));
        Page<MarkQuestionVO> result = baseMapper.pageFavorite(p, userId);
        result.getRecords().forEach(view -> history(userId, view));
        return PageResult.of(result.getTotal(), result.getCurrent(), result.getSize(), result.getRecords());
    }
    private void history(Long userId, MarkQuestionVO view) {
        PracticeRecord latest = attempts.selectOne(new LambdaQueryWrapper<PracticeRecord>()
            .eq(PracticeRecord::getUserId, userId).eq(PracticeRecord::getQuestionId, view.getQuestionId())
            .isNotNull(PracticeRecord::getIsCorrect).eq(PracticeRecord::getGradingStatus, "valid")
            .orderByDesc(PracticeRecord::getAnsweredAt).orderByDesc(PracticeRecord::getId).last("LIMIT 1"));
        QuestionHistoryView.populate(view, latest, latest == null ? questions.selectById(view.getQuestionId()) : null);
    }
}
