package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.common.ApiException;
import com.kaoyan.common.PageResult;
import com.kaoyan.entity.Question;
import com.kaoyan.mapper.QuestionMapper;
import com.kaoyan.service.QuestionService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 题库 Service 实现
 */
@Service
public class QuestionServiceImpl extends ServiceImpl<QuestionMapper, Question> implements QuestionService {

    @Override
    public List<Question> listForPractice(String subject, String difficulty,
                                          String knowledgePoint, int limit) {
        int l = Math.max(1, Math.min(limit, 100));
        return baseMapper.selectForPractice(subject, difficulty, knowledgePoint, l);
    }

    @Override
    public Question detail(Long questionId) {
        Question q = getById(questionId);
        if (q == null) {
            throw new ApiException(404, 404, "题目不存在");
        }
        return q;
    }

    @Override
    @Transactional
    public void create(Question question) {
        question.setId(null);
        if (question.getActive() == null) {
            question.setActive(1);
        }
        if (question.getVersion() == null) {
            question.setVersion(1);
        }
        if (question.getReviewStatus() == null) {
            question.setReviewStatus("PENDING_REVIEW");
        }
        save(question);
    }

    @Override
    @Transactional
    public void update(Question question) {
        if (question.getId() == null || getById(question.getId()) == null) {
            throw new ApiException(404, 404, "题目不存在");
        }
        updateById(question);
    }

    @Override
    @Transactional
    public void delete(Long questionId) {
        if (!removeById(questionId)) {
            throw new ApiException(404, 404, "题目不存在");
        }
    }

    @Override
    @Transactional
    public void submitReview(Long questionId, Long reviewerUserId, String status, String comment) {
        Question q = getById(questionId);
        if (q == null) {
            throw new ApiException(404, 404, "题目不存在");
        }
        q.setReviewStatus(status);
        q.setReviewerUserId(reviewerUserId);
        q.setReviewComment(comment);
        q.setReviewedAt(LocalDateTime.now());
        updateById(q);
    }

    @Override
    public PageResult<Question> listPendingReview(int page, int size) {
        Page<Question> p = Page.of(Math.max(page, 1), Math.min(Math.max(size, 1), 100));
        Page<Question> result = lambdaQuery()
                .eq(Question::getReviewStatus, "PENDING_REVIEW")
                .orderByAsc(Question::getStableOrder)
                .page(p);
        return PageResult.of(result.getTotal(), result.getCurrent(), result.getSize(), result.getRecords());
    }
}
