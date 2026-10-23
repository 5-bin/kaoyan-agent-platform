package com.kaoyan.controller;

import com.kaoyan.common.Result;
import com.kaoyan.security.UserContext;
import com.kaoyan.service.AssistantPrivacyService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

@RestController
@RequestMapping("/api/privacy/settings")
@RequiredArgsConstructor
public class AssistantPrivacyController {
    private final AssistantPrivacyService privacy;
    @GetMapping public Result<Map<String,Object>> get() { return Result.ok(privacy.settings(UserContext.currentUserId())); }
    @PutMapping public Result<Map<String,Object>> save(@RequestBody AssistantPrivacyService.Save input) {
        return Result.ok(privacy.save(UserContext.currentUserId(),input));
    }
}
