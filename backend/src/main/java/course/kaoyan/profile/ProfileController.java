package course.kaoyan.profile;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import course.kaoyan.auth.AuthService;
import course.kaoyan.shared.DomainTypes.*;
@RestController
@RequestMapping("/api/profile")
public class ProfileController {
    private final ProfileService service;
    public ProfileController(ProfileService service) { this.service = service; }
    private String owner(Authentication auth) { return ((AuthService.User)auth.getPrincipal()).id(); }

    @GetMapping public Object get(Authentication a) { return service.execute(owner(a), "get", null); }
    @PutMapping public Object save(Authentication a, @Valid @RequestBody ProfileContracts.Input body) {
        return service.execute(owner(a), "save", body);
    }
}
