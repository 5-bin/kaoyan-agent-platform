package course.kaoyan.catalog;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import course.kaoyan.auth.AuthService;
import course.kaoyan.common.enums.DomainTypes.*;
@RestController
@RequestMapping("/api")
public class CatalogController {
    private final CatalogService service;
    public CatalogController(CatalogService service) { this.service = service; }
    private String owner(Authentication auth) { return ((AuthService.User)auth.getPrincipal()).id(); }

    @GetMapping("/knowledge/points") public Object points(Authentication a, @RequestParam(required=false) Subject subject) { return service.knowledgePoints(subject); }
    @GetMapping("/knowledge/sources/{sourceId}") public Object source(Authentication a, @PathVariable String sourceId) { return service.source(sourceId); }
    @GetMapping("/admissions") public Object admissions(Authentication a, @RequestParam(required=false) @Min(2000) @Max(2100) Integer examYear,
            @RequestParam(required=false) String majorCode, @RequestParam(defaultValue="0") @Min(0) @Max(10000) int page) { return service.admissions(); }
    @GetMapping("/admissions/{id}") public Object admission(Authentication a, @PathVariable UUID id) { return service.admission(id); }
    @GetMapping("/questions") public Object questions(Authentication a, @RequestParam(required=false) Subject subject,
            @RequestParam(required=false) UUID knowledgePointId, @RequestParam(required=false) Difficulty difficulty,
            @RequestParam(defaultValue="0") @Min(0) @Max(10000) int page) { return service.questions(subject, knowledgePointId, difficulty, page); }
    @GetMapping("/questions/{id}") public Object question(Authentication a, @PathVariable UUID id) { return service.question(id); }
}

