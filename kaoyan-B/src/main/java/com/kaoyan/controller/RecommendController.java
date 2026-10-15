package com.kaoyan.controller;

import com.kaoyan.common.Result;
import com.kaoyan.entity.Task;
import com.kaoyan.security.UserContext;
import com.kaoyan.service.RecommendService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 择校推荐接口
 */
@Tag(name = "05. 推荐", description = "院校推荐生成与历史")
@RestController
@RequestMapping("/api/recommends")
@RequiredArgsConstructor
public class RecommendController {

    private final RecommendService recommendService;

    /**
     * 生成推荐
     */
    @Operation(summary = "生成推荐")
    @PostMapping("/generate")
    public Result<Task> generate(@RequestBody(required = false) Map<String, Object> input) {
        return Result.ok(recommendService.generate(UserContext.currentUserId(), input));
    }

    /**
     * 推荐历史
     */
    @Operation(summary = "推荐历史")
    @GetMapping
    public Result<List<Task>> list() {
        return Result.ok(recommendService.listByUser(UserContext.currentUserId()));
    }

    /**
     * 删除推荐记录
     */
    @Operation(summary = "删除推荐记录")
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable String id) {
        recommendService.delete(id, UserContext.currentUserId());
        return Result.ok();
    }
}
