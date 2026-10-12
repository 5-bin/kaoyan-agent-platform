package course.kaoyan.task;

import course.kaoyan.auth.AuthService;
import course.kaoyan.common.enums.DomainTypes.TaskType;
import course.kaoyan.common.enums.DomainTypes.Subject;
import course.kaoyan.common.exception.ApiException;
import course.kaoyan.common.exception.PendingFeature;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.Map;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class TaskController {
    private final TaskService service;
    public TaskController(TaskService service) { this.service = service; }
    public record Input(@NotBlank @Size(max=8000) String input, TaskType taskType, Subject subject,
                        Map<String, Object> preferences, java.util.UUID attemptId) {
        public Input { if (taskType == null) taskType = TaskType.knowledge_qa; }
    }
    @PostMapping("/tasks") public TaskService.View create(Authentication auth, @Valid @RequestBody Input body) {
        if (body.taskType() != TaskType.knowledge_qa) throw PendingFeature.error("择校或错题上下文构造");
        if (body.preferences() != null || body.attemptId() != null)
            throw new ApiException(400, "INVALID_INPUT", "知识问答不接受择校偏好或作答编号");
        return service.create(owner(auth), body.input(), body.taskType(), body.subject());
    }
    @GetMapping("/tasks") public TaskService.History list(Authentication auth, @RequestParam(defaultValue="0") int page,
            @RequestParam(required=false) TaskType taskType) { return service.history(owner(auth), page, taskType); }
    @GetMapping("/tasks/{id}") public TaskService.View get(Authentication auth, @PathVariable String id) { return service.get(owner(auth), id); }
    @GetMapping("/health") public Map<String, String> health() { return Map.of("status", "ok", "service", "java-business"); }
    private String owner(Authentication auth) { return ((AuthService.User) auth.getPrincipal()).id(); }
}

