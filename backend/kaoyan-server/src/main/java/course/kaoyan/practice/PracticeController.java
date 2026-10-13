package course.kaoyan.practice;

import course.kaoyan.pojo.dto.practice.PracticeContracts;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import course.kaoyan.auth.AuthService;
import course.kaoyan.common.enums.DomainTypes.*;
@RestController
@RequestMapping("/api")
public class PracticeController {
    private final PracticeService service;
    public PracticeController(PracticeService service) { this.service = service; }
    private String owner(Authentication auth) { return ((AuthService.User)auth.getPrincipal()).id(); }

    @PostMapping("/practice-sessions") public Object create(Authentication a, @Valid @RequestBody PracticeContracts.SessionInput body) { return service.createSession(owner(a), body); }
    @GetMapping("/practice-sessions") public Object sessions(Authentication a, @RequestParam(required=false) PracticeStatus status,
            @RequestParam(defaultValue="0") @Min(0) @Max(10000) int page) { return service.sessions(owner(a), status, page); }
    @GetMapping("/practice-sessions/{id}") public Object session(Authentication a, @PathVariable UUID id) { return service.session(owner(a), id); }
    @GetMapping("/practice-sessions/{id}/items/{itemId}") public Object item(Authentication a, @PathVariable UUID id, @PathVariable UUID itemId) { return service.item(owner(a), id, itemId); }
    @PutMapping("/practice-sessions/{id}/progress") public Object progress(Authentication a, @PathVariable UUID id,
            @Valid @RequestBody PracticeContracts.ProgressInput body) { return service.progress(owner(a), id, body); }
    @PostMapping("/practice-sessions/{id}/items/{itemId}/hints") public Object hints(Authentication a, @PathVariable UUID id,
            @PathVariable UUID itemId, @Valid @RequestBody PracticeContracts.HintInput body) { return service.hint(owner(a), id, itemId, body.level()); }
    @PostMapping("/practice-sessions/{id}/finish") public Object finish(Authentication a, @PathVariable UUID id) { return service.finish(owner(a), id); }
    @GetMapping("/practice-sessions/{id}/result") public Object result(Authentication a, @PathVariable UUID id) { return service.result(owner(a), id); }
    @PostMapping("/attempts") public Object submit(Authentication a, @Valid @RequestBody PracticeContracts.AttemptInput body) { return service.submit(owner(a), body); }
    @GetMapping("/attempts") public Object attempts(Authentication a, @RequestParam(defaultValue="0") @Min(0) @Max(10000) int page) { return service.attempts(owner(a), page); }
    @GetMapping("/attempts/{id}") public Object attempt(Authentication a, @PathVariable UUID id) { return service.attempt(owner(a), id); }
    @GetMapping("/wrong-questions") public Object wrong(Authentication a, @RequestParam(required=false) WrongStatus status,
            @RequestParam(defaultValue="0") @Min(0) @Max(10000) int page) { return service.wrongQuestions(owner(a), status, page); }
    @GetMapping("/wrong-questions/{id}") public Object wrongDetail(Authentication a, @PathVariable UUID id) { return service.wrongQuestion(owner(a), id); }
    @GetMapping("/favorites") public Object favorites(Authentication a, @RequestParam(defaultValue="0") @Min(0) @Max(10000) int page) { return service.favorites(owner(a), page); }
    @PutMapping("/favorites/{questionId}") public Object favorite(Authentication a, @PathVariable UUID questionId) { return service.favorite(owner(a), questionId); }
    @DeleteMapping("/favorites/{questionId}") public Object unfavorite(Authentication a, @PathVariable UUID questionId) { return service.unfavorite(owner(a), questionId); }
}


