package com.kaoyan.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.kaoyan.common.PageResult;
import com.kaoyan.entity.Question;
import com.kaoyan.dto.request.QuestionEntryRequest;
import com.kaoyan.dto.request.QuestionUpdateRequest;

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
     * @param request 可编辑题目与来源信息
     * @return 已保存的待审核题目
     */
    Question create(QuestionEntryRequest request);

    /** Validates every row and existing duplicates without writing. */
    List<Question> previewImport(List<QuestionEntryRequest> entries);

    /** Revalidates and persists the entire batch in one transaction. */
    List<Question> importQuestions(List<QuestionEntryRequest> entries);

    /**
     * 更新题目
     *
     * @param questionId 题目 ID
     * @param request 完整的可编辑题目与来源信息
     * @return 已保存的新待审核版本
     */
    Question update(Long questionId, QuestionUpdateRequest request);

    /** Toggle an approved question without changing content, provenance, audit or practice records. */
    Question changeActive(Long questionId, Integer active, Integer version);

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
     * @param version        管理员读取的题目版本
     */
    void submitReview(Long questionId, Long reviewerUserId, String status, String comment, Integer version);

    /**
     * 待审核题目分页
     *
     * @param page 页码
     * @param size 每页条数
     * @return 分页结果
     */
    PageResult<Question> listPendingReview(int page, int size);
}
