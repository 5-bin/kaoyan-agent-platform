package com.kaoyan.controller;

import com.kaoyan.common.PageResult;
import com.kaoyan.common.Result;
import com.kaoyan.dto.request.AnswerRequest;
import com.kaoyan.dto.request.StartSessionRequest;
import com.kaoyan.dto.response.ReviewRecordVO;
import com.kaoyan.dto.response.AnswerVO;
import com.kaoyan.dto.response.PracticeRecordVO;
import com.kaoyan.dto.response.SessionSummaryVO;
import com.kaoyan.entity.Task;
import com.kaoyan.security.UserContext;
import com.kaoyan.service.PracticeService;
import com.kaoyan.service.TaskService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 刷题接口
 */
@Tag(name = "07. 刷题", description = "刷题批次、作答与总结")
@RestController
@RequestMapping("/api/practice")
@RequiredArgsConstructor
public class PracticeController {

    private final PracticeService practiceService;
    private final TaskService taskService;

    /**
     * 开始批次
     */
    @Operation(summary = "开始一次刷题批次")
    @PostMapping("/sessions")
    public Result<Map<String, String>> start(@Valid @RequestBody StartSessionRequest req) {
        String sessionId = practiceService.startSession(
                UserContext.currentUserId(), req.subject(), req.difficulty(), req.count());
        return Result.ok(Map.of("sessionId", sessionId));
    }

    /**
     * 作答
     */
    @Operation(summary = "作答一题")
    @PostMapping("/sessions/{sessionId}/answer")
    public Result<AnswerVO> answer(@PathVariable String sessionId,
                               @Valid @RequestBody AnswerRequest req) {
        return Result.ok(practiceService.answer(UserContext.currentUserId(), sessionId, req.questionId(), req.answer()));
    }

    /**
     * 批次总结
     */
    @Operation(summary = "批次总结")
    @GetMapping("/sessions/{sessionId}/summary")
    public Result<Map<String, Object>> summary(@PathVariable String sessionId) {
        return Result.ok(practiceService.sessionSummary(UserContext.currentUserId(), sessionId));
    }

    @Operation(summary = "触发 AI 总结", description = "做完一批题后调用，结果落 task 表")
    @PostMapping("/sessions/{sessionId}/ai-summary")
    public Result<Task> aiSummary(@PathVariable String sessionId) {
        return Result.ok(taskService.submit(
                UserContext.currentUserId(),
                "PRACTICE_SUMMARY",
                Map.of("sessionId", sessionId)));
    }

    /**
     * 批次列表
     */
    @Operation(summary = "我的批次列表")
    @GetMapping("/sessions")
    public Result<List<String>> sessions() {
        return Result.ok(practiceService.listSessions(UserContext.currentUserId()));
    }

    @Operation(summary = "我的批次分页汇总")
    @GetMapping("/sessions/page")
    public Result<PageResult<SessionSummaryVO>> sessionsPage(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "10") int pageSize) {
        return Result.ok(practiceService.pageSessions(UserContext.currentUserId(), pageNum, pageSize));
    }

    /**
     * 批次详情
     */
    @Operation(summary = "批次详情")
    @GetMapping("/sessions/{sessionId}")
    public Result<List<PracticeRecordVO>> detail(@PathVariable String sessionId) {
        return Result.ok(practiceService.sessionDetail(UserContext.currentUserId(), sessionId).stream().map(PracticeRecordVO::from).toList());
    }

    @Operation(summary = "批次回顾分页（含题目详情）")
    @GetMapping("/sessions/{sessionId}/review")
    public Result<PageResult<ReviewRecordVO>> review(
            @PathVariable String sessionId,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "10") int pageSize) {
        return Result.ok(practiceService.pageReview(UserContext.currentUserId(), sessionId, pageNum, pageSize));
    }

    /**
     * 放弃批次
     */
    @Operation(summary = "放弃批次")
    @DeleteMapping("/sessions/{sessionId}")
    public Result<Void> abandon(@PathVariable String sessionId) {
        practiceService.abandonSession(UserContext.currentUserId(), sessionId);
        return Result.ok();
    }
}
