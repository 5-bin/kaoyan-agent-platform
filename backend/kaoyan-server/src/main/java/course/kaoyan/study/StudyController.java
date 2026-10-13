package course.kaoyan.study;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import course.kaoyan.auth.AuthService;
import course.kaoyan.common.enums.DomainTypes.*;
@RestController
@RequestMapping("/api/study")
public class StudyController {
    private final StudyService service;
    public StudyController(StudyService service) { this.service = service; }
    private String owner(Authentication auth) { return ((AuthService.User)auth.getPrincipal()).id(); }

    @GetMapping("/summary") public Object summary(Authentication a, @RequestParam(required=false) java.time.LocalDate from,
            @RequestParam(required=false) java.time.LocalDate to) {
        if (from != null && to != null && from.isAfter(to)) throw new course.kaoyan.common.exception.ApiException(400, "INVALID_INPUT", "开始日期不能晚于结束日期");
        return service.summary(owner(a), from, to);
    }
}

