package com.kaoyan.controller;

import com.kaoyan.common.PageResult;
import com.kaoyan.common.Result;
import com.kaoyan.dto.query.PageQuery;
import com.kaoyan.dto.query.QuestionPracticeQuery;
import com.kaoyan.dto.request.QuestionEntryRequest;
import com.kaoyan.dto.request.QuestionImportRequest;
import com.kaoyan.dto.response.QuestionImportVO;
import com.kaoyan.dto.request.QuestionUpdateRequest;
import com.kaoyan.dto.request.QuestionActiveRequest;
import com.kaoyan.dto.request.QuestionReviewRequest;
import com.kaoyan.entity.Question;
import com.kaoyan.dto.response.StudentQuestionVO;
import com.kaoyan.common.ApiException;
import com.kaoyan.service.QuestionHistoryView;
import com.kaoyan.security.UserContext;
import com.kaoyan.service.QuestionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 题库接口
 */
@Tag(name = "06. 题库", description = "题目查询、后台维护与审核")
@RestController
@RequestMapping("/api/questions")
@RequiredArgsConstructor
public class QuestionController {

    private final QuestionService questionService;

    /**
     * 抽题
     */
    @Operation(summary = "刷题抽题", description = "按科目/难度/知识点抽题")
    @GetMapping("/practice")
    public Result<List<StudentQuestionVO>> practice(QuestionPracticeQuery query) {
        return Result.ok(questionService.listForPractice(
                query.subject(), query.difficulty(), query.knowledgePoint(), query.effectiveLimit())
                .stream().map(StudentQuestionVO::from).toList());
    }

    /**
     * 题目详情
     */
    @Operation(summary = "题目详情")
    @GetMapping("/{id}")
    public Result<StudentQuestionVO> detail(@PathVariable Long id) {
        Question q = questionService.detail(id);
        if (!QuestionHistoryView.playable(q)) throw new ApiException(404, 404, "题目不存在或不可练习");
        return Result.ok(StudentQuestionVO.from(q));
    }

    /**
     * 待审核题目
     */
    @Operation(summary = "待审核题目分页")
    @GetMapping("/admin/pending")
    public Result<PageResult<Question>> pending(PageQuery query) {
        return Result.ok(questionService.listPendingReview(query.pageNum(), query.pageSize()));
    }

    /**
     * 新建题目
     */
    @Operation(summary = "新建题目")
    @PostMapping("/admin")
    public Result<Question> create(@Valid @RequestBody QuestionEntryRequest request) {
        return Result.ok(questionService.create(request));
    }

    @Operation(summary = "校验批量导入题目（不写入）")
    @PostMapping("/admin/import/preview")
    public Result<QuestionImportVO> previewImport(@Valid @RequestBody QuestionImportRequest request) {
        var questions = questionService.previewImport(request.questions());
        return Result.ok(new QuestionImportVO(questions.size(), questions));
    }

    @Operation(summary = "整批导入待审核题目")
    @PostMapping("/admin/import")
    public Result<QuestionImportVO> importQuestions(@Valid @RequestBody QuestionImportRequest request) {
        var questions = questionService.importQuestions(request.questions());
        return Result.ok(new QuestionImportVO(questions.size(), questions));
    }

    @Operation(summary = "管理端题目完整详情")
    @GetMapping("/admin/{id}")
    public Result<Question> adminDetail(@PathVariable Long id) {
        return Result.ok(questionService.detail(id));
    }

    /**
     * 更新题目
     */
    @Operation(summary = "更新题目")
    @PutMapping("/admin/{id}")
    public Result<Question> update(@PathVariable Long id, @Valid @RequestBody QuestionUpdateRequest request) {
        return Result.ok(questionService.update(id, request));
    }

    @Operation(summary = "停用或重新启用已审核题目")
    @PutMapping("/admin/{id}/active")
    public Result<Question> active(@PathVariable Long id, @Valid @RequestBody QuestionActiveRequest request) {
        return Result.ok(questionService.changeActive(id, request.active(), request.version()));
    }

    /**
     * 删除题目
     */
    @Operation(summary = "删除题目")
    @DeleteMapping("/admin/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        questionService.delete(id);
        return Result.ok();
    }

    /**
     * 审核题目
     */
    @Operation(summary = "审核题目")
    @PostMapping("/admin/{id}/review")
    public Result<Void> review(@PathVariable Long id, @Valid @RequestBody QuestionReviewRequest req) {
        questionService.submitReview(id, UserContext.currentUserId(), req.status(), req.comment(), req.version());
        return Result.ok();
    }
}
