package com.kaoyan.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.kaoyan.common.PageResult;
import com.kaoyan.entity.Question;

import java.util.List;

/**
 * 题库 Service
 */
public interface QuestionService extends IService<Question> {

    /**
     * 抽题用于刷题
     *
     * @param subject        科目（可空）
     * @param difficulty     难度（可空）
     * @param knowledgePoint 知识点（可空）
     * @param limit          数量
     * @return 题目列表
     */
    List<Question> listForPractice(String subject, String difficulty,
                                   String knowledgePoint, int limit);

    /**
     * 题目详情
     *
     * @param questionId 题目 ID
     * @return 题目
     */
    Question detail(Long questionId);

    /**
     * 新建题目
     *
     * @param question 题目
     */
    void create(Question question);

    /**
     * 更新题目
     *
     * @param question 题目
     */
    void update(Question question);

    /**
     * 删除题目
     *
     * @param questionId 题目 ID
     */
    void delete(Long questionId);

    /**
     * 提交审核
     *
     * @param questionId     题目 ID
     * @param reviewerUserId 审核人 ID
     * @param status         审核结果
     * @param comment        审核意见
     */
    void submitReview(Long questionId, Long reviewerUserId, String status, String comment);

    /**
     * 待审核题目分页
     *
     * @param page 页码
     * @param size 每页条数
     * @return 分页结果
     */
    PageResult<Question> listPendingReview(int page, int size);
}
