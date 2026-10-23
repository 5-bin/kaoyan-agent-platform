package com.kaoyan.controller;

import com.kaoyan.common.Result;
import com.kaoyan.security.UserContext;
import com.kaoyan.service.ConversationService;
import com.kaoyan.service.PersonalDocumentService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import java.util.Map;

@RestController
@RequestMapping("/api/conversations")
@RequiredArgsConstructor
public class ConversationController {
    private final ConversationService conversations;
    @PostMapping public Result<Map<String,Object>> create() { return Result.ok(conversations.create(UserContext.currentUserId())); }
    @DeleteMapping public Result<Void> clearAll() { conversations.clear(UserContext.currentUserId(),null); return Result.ok(); }
    @DeleteMapping("/{id}") public Result<Void> clear(@PathVariable String id) { conversations.clear(UserContext.currentUserId(),id); return Result.ok(); }
    @PostMapping("/{id}/actions/{actionId}/confirm") public Result<Map<String,Object>> confirm(@PathVariable String id,@PathVariable String actionId) {
        return Result.ok(conversations.confirm(UserContext.currentUserId(),id,actionId));
    }
    @PostMapping("/{id}/actions/{actionId}/dismiss") public Result<Map<String,Object>> dismiss(@PathVariable String id,@PathVariable String actionId) {
        return Result.ok(conversations.dismiss(UserContext.currentUserId(),id,actionId));
    }
    @GetMapping public Result<Map<String,Object>> list(@RequestParam(defaultValue="1") int pageNum,@RequestParam(defaultValue="20") int pageSize) {
        return Result.ok(conversations.list(UserContext.currentUserId(),pageNum,pageSize));
    }
    @GetMapping("/{id}/messages") public Result<Map<String,Object>> messages(@PathVariable String id,@RequestParam(defaultValue="1") int pageNum,@RequestParam(defaultValue="20") int pageSize) {
        return Result.ok(conversations.messages(UserContext.currentUserId(),id,pageNum,pageSize));
    }
    @PostMapping("/{id}/messages") public Result<Map<String,Object>> send(@PathVariable String id,@RequestBody ConversationService.Send input) {
        return Result.ok(conversations.send(UserContext.currentUserId(),id,input));
    }
    @PostMapping("/{id}/messages/{messageId}/retry") public Result<Map<String,Object>> retry(@PathVariable String id,@PathVariable String messageId,@RequestBody ConversationService.Retry input) {
        return Result.ok(conversations.retry(UserContext.currentUserId(),id,messageId,input));
    }
    @GetMapping(value="/{id}/generations/{taskId}/stream",produces="text/event-stream") public SseEmitter stream(@PathVariable String id,@PathVariable String taskId,jakarta.servlet.http.HttpServletResponse response) {
        response.setHeader("Cache-Control","no-store");
        response.setHeader("X-Accel-Buffering","no");
        return conversations.subscribe(UserContext.currentUserId(),id,taskId);
    }
    @PostMapping("/{id}/generations/{taskId}/cancel") public Result<Map<String,Object>> cancel(@PathVariable String id,@PathVariable String taskId) {
        return Result.ok(conversations.cancel(UserContext.currentUserId(),id,taskId));
    }
    @PostMapping("/{id}/generations/{taskId}/apply-document") public Result<Map<String,Object>> apply(@PathVariable String id,@PathVariable String taskId,@RequestBody(required=false) PersonalDocumentService.Save input) {
        return Result.ok(conversations.apply(UserContext.currentUserId(),id,taskId,input));
    }
}
