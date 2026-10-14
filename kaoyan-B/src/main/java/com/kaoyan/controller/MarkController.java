package com.kaoyan.controller;

import com.kaoyan.common.PageResult;
import com.kaoyan.common.Result;
import com.kaoyan.dto.response.MarkQuestionVO;
import com.kaoyan.entity.UserQuestionMark;
import com.kaoyan.security.UserContext;
import com.kaoyan.service.UserQuestionMarkService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 错题与收藏接口
 */
@Tag(name = "08. 错题收藏", description = "错题本与题目收藏")
@RestController
@RequestMapping("/api/marks")
@RequiredArgsConstructor
public class MarkController {

    private final UserQuestionMarkService markService;

    /**
     * 标记错题
     */
    @Operation(summary = "标记为错题")
    @PostMapping("/wrong/{questionId}")
    public Result<Void> markWrong(@PathVariable Long questionId) {
        markService.markWrong(UserContext.currentUserId(), questionId);
        return Result.ok();
    }

    /**
     * 移出错题本
     */
    @Operation(summary = "移出错题本")
    @DeleteMapping("/wrong/{questionId}")
    public Result<Void> removeWrong(@PathVariable Long questionId) {
        markService.removeWrong(UserContext.currentUserId(), questionId);
        return Result.ok();
    }

    /**
     * 收藏
     */
    @Operation(summary = "收藏题目")
    @PostMapping("/favorite/{questionId}")
    public Result<Void> favorite(@PathVariable Long questionId) {
        markService.toggleFavorite(UserContext.currentUserId(), questionId, true);
        return Result.ok();
    }

    /**
     * 取消收藏
     */
    @Operation(summary = "取消收藏")
    @DeleteMapping("/favorite/{questionId}")
    public Result<Void> unfavorite(@PathVariable Long questionId) {
        markService.toggleFavorite(UserContext.currentUserId(), questionId, false);
        return Result.ok();
    }

    @Operation(summary = "错题列表（分页，含题目详情）")
    @GetMapping("/wrong")
    public Result<PageResult<MarkQuestionVO>> wrongList(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        return Result.ok(markService.pageWrong(UserContext.currentUserId(), pageNum, pageSize));
    }

    @Operation(summary = "收藏列表（分页，含题目详情）")
    @GetMapping("/favorite")
    public Result<PageResult<MarkQuestionVO>> favoriteList(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        return Result.ok(markService.pageFavorite(UserContext.currentUserId(), pageNum, pageSize));
    }
}
