package com.kaoyan.controller;

import com.kaoyan.common.Result;
import com.kaoyan.security.UserContext;
import com.kaoyan.service.PersonalDocumentService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

@RestController
@RequestMapping("/api/personal-documents")
@RequiredArgsConstructor
public class PersonalDocumentController {
    private final PersonalDocumentService documents;
    @GetMapping
    public Result<Map<String,Object>> list(@RequestParam(defaultValue="1") int pageNum,@RequestParam(defaultValue="20") int pageSize) {
        return Result.ok(documents.list(UserContext.currentUserId(),pageNum,pageSize));
    }
    @GetMapping("/{id}")
    public Result<Map<String,Object>> get(@PathVariable String id) { return Result.ok(documents.get(UserContext.currentUserId(),id)); }
    @GetMapping("/{id}/versions")
    public Result<Map<String,Object>> versions(@PathVariable String id,@RequestParam(defaultValue="1") int pageNum,@RequestParam(defaultValue="20") int pageSize) {
        return Result.ok(documents.versions(UserContext.currentUserId(),id,pageNum,pageSize));
    }
    @PostMapping
    public Result<Map<String,Object>> create(@RequestBody PersonalDocumentService.Save input) {
        return Result.ok(documents.save(UserContext.currentUserId(),null,input,null));
    }
    @GetMapping("/{id}/versions/{version}")
    public Result<Map<String,Object>> version(@PathVariable String id,@PathVariable int version) {
        return Result.ok(documents.version(UserContext.currentUserId(),id,version));
    }
    @PutMapping("/{id}")
    public Result<Map<String,Object>> update(@PathVariable String id,@RequestBody PersonalDocumentService.Save input) {
        return Result.ok(documents.save(UserContext.currentUserId(),id,input,null));
    }
}
