package com.kaoyan.controller;

import com.kaoyan.common.Result;
import com.kaoyan.security.UserContext;
import com.kaoyan.util.OssUtil;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

/**
 * 文件接口
 */
@Tag(name = "10. 文件", description = "文件上传与删除")
@RestController
@RequestMapping("/api/files")
@RequiredArgsConstructor
public class FileController {

    private final OssUtil ossUtil;

    /**
     * 上传文件
     *
     * @param file   文件
     * @param module 业务模块（头像传 avatar）
     * @return url 与 objectKey
     */
    @Operation(summary = "上传文件", description = "module 可选，默认 common；头像传 avatar")
    @PostMapping("/upload")
    public Result<Map<String, String>> upload(@RequestParam("file") MultipartFile file,
                                               @RequestParam(value = "module", required = false, defaultValue = "common") String module) {
        UserContext.currentUserId();
        String objectKey = ossUtil.upload(file, module);
        return Result.ok(Map.of("url", ossUtil.buildUrl(objectKey), "objectKey", objectKey));
    }

    /**
     * 删除文件
     *
     * @param objectKey 对象键
     */
    @Operation(summary = "删除文件", description = "按 objectKey 删除")
    @DeleteMapping
    public Result<Void> delete(@RequestParam("objectKey") String objectKey) {
        UserContext.currentUserId();
        ossUtil.delete(objectKey);
        return Result.ok();
    }
}
