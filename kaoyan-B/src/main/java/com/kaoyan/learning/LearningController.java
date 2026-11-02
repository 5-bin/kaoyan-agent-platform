package com.kaoyan.learning;

import com.kaoyan.common.*;
import com.kaoyan.security.UserContext;
import com.kaoyan.learning.LearningContracts.*;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.web.bind.annotation.*;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import java.util.*;

@RestController
@RequiredArgsConstructor
public class LearningController {
    private final ObjectProvider<ManagedPracticeService> practice;
    private final ObjectProvider<LearningProfiles> profiles;
    private final ObjectProvider<LearningRecommendations> recommendations;
    private static <T> T enabled(ObjectProvider<T> provider) {
        T value=provider.getIfAvailable();if(value==null)throw new ApiException(503,"诊断与学情功能尚未启用，请先完成V13迁移并配置开关");return value;
    }
    @GetMapping("/api/learning/status") public Result<Map<String,Object>> status() {return Result.ok(Map.of("enabled",practice.getIfAvailable()!=null));}
    @PostMapping("/api/diagnostics/sessions") public Result<Map<String,Object>> diagnose() {return Result.ok(enabled(practice).diagnose(UserContext.currentUserId()));}
    @GetMapping("/api/practice/sessions/{id}/state") public Result<State> state(@PathVariable String id) {return Result.ok(enabled(practice).state(UserContext.currentUserId(),id));}
    @PutMapping("/api/practice/sessions/{id}/progress") public Result<State> progress(@PathVariable String id,@Valid @RequestBody Progress req) {return Result.ok(enabled(practice).progress(UserContext.currentUserId(),id,req));}
    @PostMapping("/api/practice/sessions/{id}/finish") public Result<Map<String,Object>> finish(@PathVariable String id) {return Result.ok(enabled(practice).finish(UserContext.currentUserId(),id));}
    @GetMapping("/api/practice/sessions/{id}/result") public Result<Map<String,Object>> result(@PathVariable String id) {return Result.ok(enabled(practice).result(UserContext.currentUserId(),id));}
    @PostMapping("/api/practice/sessions/{id}/items/{item}/hints") public Result<Map<String,Object>> hint(@PathVariable String id,@PathVariable long item,@Valid @RequestBody Hint req) {return Result.ok(enabled(practice).hint(UserContext.currentUserId(),id,item,req.level()));}
    @GetMapping("/api/learning/profile") public Result<Profile> profile() {return Result.ok(enabled(profiles).profile(UserContext.currentUserId()));}
    @GetMapping("/api/learning/profile/history") public Result<Map<String,Object>> history(@RequestParam(defaultValue="1") int pageNum,@RequestParam(defaultValue="10") int pageSize) {return Result.ok(enabled(profiles).history(UserContext.currentUserId(),pageNum,pageSize));}
    @GetMapping("/api/learning/recommendation-settings") public Result<Map<String,Object>> settings() {return Result.ok(enabled(recommendations).settings(UserContext.currentUserId()));}
    @PutMapping("/api/learning/recommendation-settings") public Result<Map<String,Object>> settings(@Valid @RequestBody Settings req) {return Result.ok(enabled(recommendations).save(UserContext.currentUserId(),req));}
    @PostMapping("/api/learning/admin/blueprints") public Result<Map<String,Object>> publish(@Valid @RequestBody Blueprint req) {
        admin();enabled(profiles).publish(req,UserContext.currentUserId());return Result.ok(Map.of("id",req.id(),"version",req.version()));
    }
    @PostMapping("/api/learning/admin/historical-metrics") public Result<Map<String,Object>> metric(@Valid @RequestBody Metric req) {
        admin();return Result.ok(Map.of("id",enabled(recommendations).addMetric(req,UserContext.currentUserId())));
    }
    @PostMapping("/api/questions/admin/{id}/versions") public Result<Map<String,Object>> revision(@PathVariable long id,@Valid @RequestBody Revision req) {
        admin();return Result.ok(enabled(practice).publishRevision(id,req,UserContext.currentUserId()));
    }
    @PostMapping("/api/questions/admin/{id}/versions/{version}/withdraw") public Result<Void> withdraw(@PathVariable long id,@PathVariable int version,@Valid @RequestBody Withdraw req) {
        admin();enabled(practice).withdraw(id,version,req.reason());return Result.ok();
    }
    private static void admin() {if(!"ADMIN".equals(UserContext.currentRole()))throw new ApiException(403,"仅管理员可操作");}
}
