package com.kaoyan.controller;

import com.kaoyan.common.PageResult;
import com.kaoyan.common.Result;
import com.kaoyan.dto.query.DocumentAdminQuery;
import com.kaoyan.dto.query.DocumentQuery;
import com.kaoyan.dto.request.ReviewRequest;
import com.kaoyan.entity.Document;
import com.kaoyan.security.UserContext;
import com.kaoyan.service.DocumentService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 备考资料接口
 */
@Tag(name = "03. 资料", description = "备考资料浏览与后台管理")
@RestController
@RequestMapping("/api/documents")
@RequiredArgsConstructor
public class DocumentController {

    private final DocumentService documentService;

    /**
     * 已发布资料列表
     */
    @Operation(summary = "已发布资料列表")
    @GetMapping
    public Result<List<Document>> listPublished(DocumentQuery query) {
        return Result.ok(documentService.listPublished(query.subject()));
    }

    /**
     * 后台按状态分页查询
     */
    @Operation(summary = "后台资料列表（按状态）")
    @GetMapping("/admin/list")
    public Result<PageResult<Document>> adminList(DocumentAdminQuery query) {
        return Result.ok(documentService.listByStatus(
                query.status(), query.pageNum(), query.pageSize()));
    }

    /**
     * 新建资料
     */
    @Operation(summary = "新建资料")
    @PostMapping("/admin")
    public Result<Document> create(@RequestBody Document doc) {
        return Result.ok(documentService.create(UserContext.currentUserId(), doc));
    }

    /**
     * 更新资料
     */
    @Operation(summary = "更新资料")
    @PutMapping("/admin/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody Document doc) {
        documentService.update(id, doc);
        return Result.ok();
    }

    /**
     * 删除资料
     */
    @Operation(summary = "删除资料")
    @DeleteMapping("/admin/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        documentService.delete(id);
        return Result.ok();
    }

    /**
     * 审核资料
     */
    @Operation(summary = "审核资料")
    @PostMapping("/admin/{id}/review")
    public Result<Void> review(@PathVariable Long id, @Valid @RequestBody ReviewRequest req) {
        documentService.review(id, UserContext.currentUserId(), req.status(), req.comment());
        return Result.ok();
    }
}
