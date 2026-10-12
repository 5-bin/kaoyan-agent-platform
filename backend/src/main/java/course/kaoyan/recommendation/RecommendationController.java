package course.kaoyan.recommendation;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import course.kaoyan.auth.AuthService;
import course.kaoyan.shared.DomainTypes.*;
@RestController
@RequestMapping("/api/recommendations")
public class RecommendationController {
    private final RecommendationService service;
    public RecommendationController(RecommendationService service) { this.service = service; }
    private String owner(Authentication auth) { return ((AuthService.User)auth.getPrincipal()).id(); }

    @GetMapping public Object list(Authentication a, @RequestParam(defaultValue="0") @Min(0) @Max(10000) int page) { return service.execute(owner(a), "list", page); }
    @GetMapping("/{id}") public Object get(Authentication a, @PathVariable UUID id) { return service.execute(owner(a), "get", id); }
}
