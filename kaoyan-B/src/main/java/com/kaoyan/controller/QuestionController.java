package com.kaoyan.controller;

import com.kaoyan.common.PageResult;
import com.kaoyan.common.Result;
import com.kaoyan.dto.query.PageQuery;
import com.kaoyan.dto.query.QuestionPracticeQuery;
import com.kaoyan.dto.request.ReviewRequest;
import com.kaoyan.entity.Question;
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
    public Result<List<Question>> practice(QuestionPracticeQuery query) {
        return Result.ok(questionService.listForPractice(
                query.subject(), query.difficulty(), query.knowledgePoint(), query.effectiveLimit()));
    }

    /**
     * 题目详情
     */
    @Operation(summary = "题目详情")
    @GetMapping("/{id}")
    public Result<Question> detail(@PathVariable Long id) {
        return Result.ok(questionService.detail(id));
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
    public Result<Question> create(@RequestBody Question question) {
        questionService.create(question);
        return Result.ok(question);
    }

    /**
     * 更新题目
     */
    @Operation(summary = "更新题目")
    @PutMapping("/admin/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody Question question) {
        question.setId(id);
        questionService.update(question);
        return Result.ok();
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
    public Result<Void> review(@PathVariable Long id, @Valid @RequestBody ReviewRequest req) {
        questionService.submitReview(id, UserContext.currentUserId(), req.status(), req.comment());
        return Result.ok();
    }
}
