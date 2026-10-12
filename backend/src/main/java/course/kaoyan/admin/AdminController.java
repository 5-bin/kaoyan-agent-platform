package course.kaoyan.admin;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import course.kaoyan.auth.AuthService;
import course.kaoyan.shared.DomainTypes.*;
@RestController
@RequestMapping("/api/admin")
public class AdminController {
    private final AdminService service;
    public AdminController(AdminService service) { this.service = service; }
    private String owner(Authentication auth) { return ((AuthService.User)auth.getPrincipal()).id(); }

    @GetMapping("/documents") public Object documents(Authentication a) { return service.execute(owner(a), "documents", null); }
    @PostMapping("/documents") public Object documentCreate(Authentication a, @Valid @RequestBody AdminContracts.DocumentInput body) { return service.execute(owner(a), "document-create", body); }
    @PutMapping("/documents/{id}") public Object documentUpdate(Authentication a, @PathVariable UUID id, @Valid @RequestBody AdminContracts.DocumentInput body) { return service.execute(owner(a), "document-update", body); }
    @PostMapping("/documents/{id}/review") public Object documentReview(Authentication a, @PathVariable UUID id, @Valid @RequestBody AdminContracts.ReviewInput body) { return service.execute(owner(a), "document-review", body); }
    @GetMapping("/admissions") public Object admissions(Authentication a) { return service.execute(owner(a), "admissions", null); }
    @PostMapping("/admissions") public Object admissionCreate(Authentication a, @Valid @RequestBody AdminContracts.AdmissionInput body) { return service.execute(owner(a), "admission-create", body); }
    @PutMapping("/admissions/{id}") public Object admissionUpdate(Authentication a, @PathVariable UUID id, @Valid @RequestBody AdminContracts.AdmissionInput body) { return service.execute(owner(a), "admission-update", body); }
    @PostMapping("/admissions/{id}/review") public Object admissionReview(Authentication a, @PathVariable UUID id, @Valid @RequestBody AdminContracts.ReviewInput body) { return service.execute(owner(a), "admission-review", body); }
    @GetMapping("/questions") public Object questions(Authentication a) { return service.execute(owner(a), "questions", null); }
    @PostMapping("/questions") public Object questionCreate(Authentication a, @Valid @RequestBody AdminContracts.QuestionInput body) { return service.execute(owner(a), "question-create", body); }
    @PutMapping("/questions/{id}") public Object questionUpdate(Authentication a, @PathVariable UUID id, @Valid @RequestBody AdminContracts.QuestionInput body) { return service.execute(owner(a), "question-update", body); }
    @PostMapping("/questions/{id}/review") public Object questionReview(Authentication a, @PathVariable UUID id, @Valid @RequestBody AdminContracts.ReviewInput body) { return service.execute(owner(a), "question-review", body); }
    @PostMapping("/releases") public Object release(Authentication a) { return service.execute(owner(a), "release-create", null); }
    @PostMapping("/releases/{id}/activate") public Object activate(Authentication a, @PathVariable UUID id) { return service.execute(owner(a), "activate", id); }
}
