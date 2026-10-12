package course.kaoyan.auth;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/auth")
public class AuthController {
    private final AuthService service;
    public AuthController(AuthService service) { this.service = service; }
    public record Credentials(@NotBlank @Size(max=32) String username, @NotBlank @Size(max=72) String password) {}
    @PostMapping("/register") public AuthService.Login register(@Valid @RequestBody Credentials body) { return service.register(body.username(), body.password()); }
    @PostMapping("/login") public AuthService.Login login(@Valid @RequestBody Credentials body) { return service.login(body.username(), body.password()); }
    @GetMapping("/me") public Object me(Authentication authentication) { return authentication.getPrincipal(); }
    @PostMapping("/logout") public void logout(@RequestHeader("Authorization") String header) { service.logout(header.substring(7)); }
}
