package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.common.ApiException;
import com.kaoyan.common.PageResult;
import com.kaoyan.entity.Question;
import com.kaoyan.dto.request.QuestionEntryRequest;
import com.kaoyan.dto.request.QuestionUpdateRequest;
import com.kaoyan.mapper.QuestionMapper;
import com.kaoyan.service.QuestionService;
import jakarta.validation.Validator;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;

/**
 * 题库 Service 实现
 */
@Service
@RequiredArgsConstructor
public class QuestionServiceImpl extends ServiceImpl<QuestionMapper, Question> implements QuestionService {

    private final Validator validator;

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
    public Question create(QuestionEntryRequest request) {
        Question question = unpublishedEntry(request);
        save(question);
        return question;
    }

    private Question unpublishedEntry(QuestionEntryRequest request) {
        Question question = entry(request);
        question.setActive(1);
        question.setVersion(1);
        question.setStableOrder(0);
        question.setQuestionType("SINGLE_CHOICE");
        question.setReviewStatus("PENDING_REVIEW");
        return question;
    }

    @Override
    public List<Question> previewImport(List<QuestionEntryRequest> entries) {
        if (entries == null || entries.isEmpty() || entries.size() > 50)
            throw new ApiException(400, 400, "每批请导入1至50道题目");
        List<Question> result = new ArrayList<>();
        Map<List<String>, Integer> seen = new HashMap<>();
        for (int i = 0; i < entries.size(); i++) {
            Question q;
            try { q = unpublishedEntry(entries.get(i)); }
            catch (ApiException error) {
                throw new ApiException(400, 400, "第" + (i + 1) + "题：" + error.getMessage());
            }
            var key = List.of(q.getSubject(), q.getContent(), q.getOptionA(), q.getOptionB(), q.getOptionC(), q.getOptionD());
            Integer first = seen.putIfAbsent(key, i + 1);
            if (first != null)
                throw new ApiException(400, 400, "第" + (i + 1) + "题与本批第" + first + "题重复，请核对题干和选项");
            var existing = lambdaQuery().select(Question::getId)
                .eq(Question::getSubject, q.getSubject()).eq(Question::getContent, q.getContent())
                .eq(Question::getOptionA, q.getOptionA()).eq(Question::getOptionB, q.getOptionB())
                .eq(Question::getOptionC, q.getOptionC()).eq(Question::getOptionD, q.getOptionD())
                .orderByAsc(Question::getId).last("LIMIT 1").one();
            if (existing != null)
                throw new ApiException(409, 409, "第" + (i + 1) + "题已存在，题目ID为" + existing.getId() + "，请先查看已有题目");
            result.add(q);
        }
        return result;
    }

    @Override
    @Transactional
    public List<Question> importQuestions(List<QuestionEntryRequest> entries) {
        // Validate all rows before the first INSERT; runtime write failures roll back the whole batch.
        List<Question> questions = previewImport(entries);
        for (Question question : questions) {
            if (!save(question)) throw new ApiException(500, 500, "导入未完成，整批已回滚");
        }
        return questions;
    }

    @Override
    @Transactional
    public Question update(Long questionId, QuestionUpdateRequest request) {
        Question existing = locked(questionId);
        requireVersion(existing, request.version());
        if (!"PENDING_REVIEW".equals(existing.getReviewStatus()) && !"REJECTED".equals(existing.getReviewStatus()))
            throw new ApiException(409, 409, "已发布题目不能原地修改，请通过后续版本发布流程修订");
        Question replacement = entry(request.entry());
        replacement.setId(questionId);
        replacement.setVersion(Math.addExact(existing.getVersion(), 1));
        replacement.setReviewStatus("PENDING_REVIEW");
        // Explicit assignments also clear optional fields and audit data when resubmitting.
        lambdaUpdate().eq(Question::getId, questionId)
            .set(Question::getSubject, replacement.getSubject()).set(Question::getKnowledgePoint, replacement.getKnowledgePoint())
            .set(Question::getDifficulty, replacement.getDifficulty()).set(Question::getContent, replacement.getContent())
            .set(Question::getOptionA, replacement.getOptionA()).set(Question::getOptionB, replacement.getOptionB())
            .set(Question::getOptionC, replacement.getOptionC()).set(Question::getOptionD, replacement.getOptionD())
            .set(Question::getAnswer, replacement.getAnswer()).set(Question::getAnalysis, replacement.getAnalysis())
            .set(Question::getSourceType, replacement.getSourceType()).set(Question::getSourceName, replacement.getSourceName())
            .set(Question::getSourceLocator, replacement.getSourceLocator()).set(Question::getPermissionNote, replacement.getPermissionNote())
            .set(Question::getVersion, replacement.getVersion()).set(Question::getReviewStatus, "PENDING_REVIEW")
            .set(Question::getReviewerUserId, null).set(Question::getReviewedAt, null)
            .set(Question::getReviewComment, null).set(Question::getSourceYear, replacement.getSourceYear())
            .set(Question::getSourceQuestionNo, replacement.getSourceQuestionNo())
            .set(Question::getUpdatedAt, LocalDateTime.now()).update();
        return detail(questionId);
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
    public void submitReview(Long questionId, Long reviewerUserId, String status, String comment, Integer version) {
        if (!"APPROVED".equals(status) && !"REJECTED".equals(status))
            throw new ApiException(400, 400, "审核结果只能为通过或驳回");
        if ((comment != null && comment.length() > 2000) || ("REJECTED".equals(status) && (comment == null || comment.isBlank())))
            throw new ApiException(400, 400, "驳回需填写原因，审核意见最多2000字");
        Question q = locked(questionId);
        requireVersion(q, version);
        if (!"PENDING_REVIEW".equals(q.getReviewStatus()))
            throw new ApiException(409, 409, "题目已被修改或审核，请重新读取最新详情");
        if ("APPROVED".equals(status)) validateEntry(storedEntry(q), false);
        q.setVersion(Math.addExact(q.getVersion(), 1));
        q.setReviewStatus(status);
        q.setReviewerUserId(reviewerUserId);
        q.setReviewComment(comment);
        q.setReviewedAt(LocalDateTime.now());
        updateById(q);
    }

    @Override
    @Transactional
    public Question changeActive(Long questionId, Integer active, Integer version) {
        if (active == null || (active != 0 && active != 1))
            throw new ApiException(400, 400, "启用状态只能为0或1");
        Question q = locked(questionId);
        requireVersion(q, version);
        if (!"APPROVED".equals(q.getReviewStatus()))
            throw new ApiException(409, 409, "仅审核通过的题目可以停用或重新启用");
        if (active.equals(q.getActive()))
            throw new ApiException(409, 409, "题目已处于该启用状态，请刷新详情");
        if (active == 1) {
            if (!"SINGLE_CHOICE".equals(q.getQuestionType()))
                throw new ApiException(400, 400, "仅支持完整的单选题，请核对题型");
            boolean legacy = q.getSourceType() == null && q.getSourceName() == null
                && q.getSourceLocator() == null && q.getSourceYear() == null
                && q.getSourceQuestionNo() == null && q.getPermissionNote() == null;
            validateEntry(storedEntry(q), legacy);
        }
        lambdaUpdate().eq(Question::getId, questionId)
            .set(Question::getActive, active).set(Question::getVersion, Math.addExact(q.getVersion(), 1))
            .set(Question::getUpdatedAt, LocalDateTime.now()).update();
        return detail(questionId);
    }

    private void requireVersion(Question q, Integer version) {
        if (version == null || version < 1 || !version.equals(q.getVersion()))
            throw new ApiException(409, 409, "题目已被修改、审核或切换状态，请重新读取最新详情");
    }

    private QuestionEntryRequest storedEntry(Question q) {
        return new QuestionEntryRequest(q.getSubject(), q.getKnowledgePoint(), q.getDifficulty(),
            q.getContent(), q.getOptionA(), q.getOptionB(), q.getOptionC(), q.getOptionD(), q.getAnswer(),
            q.getAnalysis(), q.getSourceType(), q.getSourceName(), q.getSourceLocator(), q.getSourceYear(),
            q.getSourceQuestionNo(), q.getPermissionNote());
    }

    private Question locked(Long id) {
        Question question = baseMapper.selectForUpdate(id);
        if (question == null) throw new ApiException(404, 404, "题目不存在");
        return question;
    }

    private void validateEntry(QuestionEntryRequest r, boolean legacySource) {
        Set<String> sourceFields = Set.of("sourceType", "sourceName", "sourceLocator", "sourceYear",
            "sourceQuestionNo", "permissionNote");
        if (r == null || validator.validate(r).stream().anyMatch(v ->
                !legacySource || !sourceFields.contains(v.getPropertyPath().toString())))
            throw new ApiException(400, 400, "题目或来源信息不完整，请补充后再提交");
        if ("REAL_EXAM".equals(r.sourceType()) && (r.sourceYear() == null
                || r.sourceQuestionNo() == null || r.sourceQuestionNo().isBlank()))
            throw new ApiException(400, 400, "真题必须填写年份和原题号");
    }

    private Question entry(QuestionEntryRequest r) {
        validateEntry(r, false);
        Question q = new Question();
        q.setSubject(r.subject()); q.setKnowledgePoint(r.knowledgePoint().strip()); q.setDifficulty(r.difficulty());
        q.setContent(r.content().strip()); q.setOptionA(r.optionA().strip()); q.setOptionB(r.optionB().strip());
        q.setOptionC(r.optionC().strip()); q.setOptionD(r.optionD().strip());
        q.setAnswer(r.answer().toUpperCase(java.util.Locale.ROOT)); q.setAnalysis(r.analysis().strip());
        q.setSourceType(r.sourceType()); q.setSourceName(r.sourceName().strip()); q.setSourceLocator(r.sourceLocator().strip());
        q.setSourceYear(r.sourceYear()); q.setSourceQuestionNo(r.sourceQuestionNo() == null || r.sourceQuestionNo().isBlank() ? null : r.sourceQuestionNo().strip());
        q.setPermissionNote(r.permissionNote().strip());
        return q;
    }

    @Override
    public PageResult<Question> listPendingReview(int page, int size) {
        Page<Question> p = Page.of(Math.max(page, 1), Math.min(Math.max(size, 1), 100));
        Page<Question> result = lambdaQuery()
                .eq(Question::getReviewStatus, "PENDING_REVIEW")
                .orderByAsc(Question::getStableOrder)
                .orderByAsc(Question::getId)
                .page(p);
        return PageResult.of(result.getTotal(), result.getCurrent(), result.getSize(), result.getRecords());
    }
}
