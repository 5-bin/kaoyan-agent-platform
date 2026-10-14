package com.kaoyan.controller;

import com.kaoyan.common.Result;
import com.kaoyan.dto.query.StatRangeQuery;
import com.kaoyan.entity.StudyStat;
import com.kaoyan.security.UserContext;
import com.kaoyan.service.StudyStatService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 学习统计接口
 */
@Tag(name = "09. 统计", description = "学习数据统计")
@RestController
@RequestMapping("/api/stats")
@RequiredArgsConstructor
public class StatController {

    private final StudyStatService studyStatService;

    /**
     * 今日统计
     */
    @Operation(summary = "今日统计")
    @GetMapping("/today")
    public Result<StudyStat> today() {
        return Result.ok(studyStatService.today(UserContext.currentUserId()));
    }

    /**
     * 区间统计
     */
    @Operation(summary = "区间统计")
    @GetMapping("/range")
    public Result<List<StudyStat>> range(StatRangeQuery query) {
        return Result.ok(studyStatService.range(
                UserContext.currentUserId(), query.from(), query.to()));
    }

    /**
     * 总览
     */
    @Operation(summary = "学习总览")
    @GetMapping("/overview")
    public Result<Map<String, Object>> overview() {
        return Result.ok(studyStatService.overview(UserContext.currentUserId()));
    }
}
