package com.kaoyan.controller;

import com.kaoyan.common.Result;
import com.kaoyan.dto.query.SchoolQuery;
import com.kaoyan.dto.response.SchoolOptionsVO;
import com.kaoyan.entity.School;
import com.kaoyan.service.SchoolService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 院校接口
 */
@Tag(name = "04. 院校", description = "院校搜索与详情")
@RestController
@RequestMapping("/api/schools")
@RequiredArgsConstructor
public class SchoolController {

    private final SchoolService schoolService;

    @Operation(summary = "院校筛选选项", description = "返回库内已有的省份与专业名，去除空值及重复值并排序")
    @GetMapping("/options")
    public Result<SchoolOptionsVO> options() {
        return Result.ok(schoolService.options());
    }

    /**
     * 搜索院校（GET，普通 query 参数）
     */
    @Operation(summary = "搜索院校", description = "可按省份、层次、专业名筛选；不传则查全部")
    @GetMapping
    public Result<List<School>> search(
            @Parameter(description = "省份", example = "北京")
            @RequestParam(required = false) String province,
            @Parameter(description = "层次：985/211/双一流", example = "985")
            @RequestParam(required = false) String level,
            @Parameter(description = "专业名（模糊）", example = "计算机")
            @RequestParam(required = false) String majorName) {
        return Result.ok(schoolService.search(province, level, majorName));
    }

    /**
     * 搜索院校（POST + JSON body，方便传复杂条件）
     */
    @Operation(summary = "搜索院校（POST/JSON）", description = "body 传 JSON，可按省份、层次、专业名筛选")
    @PostMapping("/search")
    public Result<List<School>> searchByBody(@RequestBody SchoolQuery query) {
        return Result.ok(schoolService.search(query.province(), query.level(), query.majorName()));
    }

    /**
     * 院校详情
     */
    @Operation(summary = "院校详情（含专业列表）")
    @GetMapping("/{schoolId}")
    public Result<Map<String, Object>> detail(@PathVariable Long schoolId) {
        return Result.ok(schoolService.detail(schoolId));
    }
}
