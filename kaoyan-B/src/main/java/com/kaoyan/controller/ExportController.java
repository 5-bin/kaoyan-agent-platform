package com.kaoyan.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.kaoyan.common.Result;
import com.kaoyan.export.ExportContracts.*;
import com.kaoyan.export.ExportService;
import com.kaoyan.security.UserContext;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import java.nio.charset.StandardCharsets;

/** Authenticated preview and download endpoints; no permanent or publicly accessible artifact URLs. */
@RestController
@RequestMapping("/api/exports")
public class ExportController {
    private final ExportService exports;
    public ExportController(ExportService exports) { this.exports = exports; }
    @PostMapping("/preview")
    public ResponseEntity<Result<Preview>> preview(@RequestBody JsonNode input) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore())
                .body(Result.ok(exports.create(UserContext.currentUserId(), Source.parse(input))));
    }
    @GetMapping("/{id}")
    public ResponseEntity<Result<Preview>> get(@PathVariable String id) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore())
                .body(Result.ok(exports.get(UserContext.currentUserId(), id)));
    }
    @GetMapping("/{id}/file")
    public ResponseEntity<byte[]> file(@PathVariable String id, @RequestParam String format) {
        File result = exports.file(UserContext.currentUserId(), id, format);
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).contentType(MediaType.parseMediaType(result.contentType()))
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment().filename(result.filename(), StandardCharsets.UTF_8).build().toString())
                .header("X-Content-Type-Options", "nosniff").body(result.bytes());
    }
}
