package com.kaoyan.controller;

import com.kaoyan.common.PageResult;
import com.kaoyan.common.Result;
import com.kaoyan.dto.query.PageQuery;
import com.kaoyan.dto.request.TaskSubmitRequest;
import com.kaoyan.entity.Task;
import com.kaoyan.security.UserContext;
import com.kaoyan.service.TaskService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * Agent 任务接口
 */
@Tag(name = "02. 任务", description = "Agent 任务提交与查询")
@RestController
@RequestMapping("/api/tasks")
@RequiredArgsConstructor
public class TaskController {

    private final TaskService taskService;

    /**
     * 提交任务
     */
    @Operation(summary = "提交任务")
    @PostMapping
    public Result<Task> submit(@Valid @RequestBody TaskSubmitRequest req) {
        return Result.ok(taskService.submit(UserContext.currentUserId(), req.taskType(), req.input()));
    }

    /**
     * 任务历史
     */
    @Operation(summary = "任务历史")
    @GetMapping
    public Result<PageResult<Task>> history(PageQuery query) {
        int page = query.pageNum();
        int size = query.pageSize();
        return Result.ok(taskService.history(UserContext.currentUserId(), page, size));
    }

    /**
     * 任务详情
     */
    @Operation(summary = "任务详情")
    @GetMapping("/{taskId}")
    public Result<Task> detail(@PathVariable String taskId) {
        return Result.ok(taskService.detail(UserContext.currentUserId(), taskId));
    }
}
