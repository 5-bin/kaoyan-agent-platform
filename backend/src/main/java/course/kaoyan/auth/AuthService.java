package course.kaoyan.auth;

import course.kaoyan.shared.ApiException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import java.util.HexFormat;
import java.util.Locale;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class AuthService {
    private final AccountRepository accounts;
    private final SessionRepository sessions;
    private final PasswordEncoder encoder;
    private final SecureRandom random = new SecureRandom();
    public AuthService(AccountRepository accounts, SessionRepository sessions, PasswordEncoder encoder) {
        this.accounts = accounts; this.sessions = sessions; this.encoder = encoder;
    }
    public record User(String id, String username, String role) {}
    public record Login(String token, Instant expiresAt, User user) {}
    public Login register(String name, String password) {
        String username = normalize(name);
        checkPassword(password);
        if (accounts.findByUsername(username).isPresent()) throw duplicate();
        Account account;
        try { account = accounts.saveAndFlush(new Account(username, encoder.encode(password))); }
        catch (DataIntegrityViolationException e) { throw duplicate(); }
        return issue(account);
    }
    public Login login(String name, String password) {
        checkPassword(password);
        Account account = accounts.findByUsername(normalize(name)).orElseThrow(this::wrongCredentials);
        if (!encoder.matches(password, account.passwordHash)) throw wrongCredentials();
        return issue(account);
    }
    private Login issue(Account account) {
        byte[] bytes = new byte[32]; random.nextBytes(bytes);
        String token = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        Instant expires = Instant.now().plusSeconds(86400);
        sessions.save(new Session(hash(token), account.id, expires));
        return new Login(token, expires, new User(account.id, account.username, account.role));
    }
    public User authenticate(String token) {
        Session session = sessions.findById(hash(token)).orElseThrow(this::unauthorized);
        if (!session.expiresAt.isAfter(Instant.now())) throw unauthorized();
        Account account = accounts.findById(session.accountId).orElseThrow(this::unauthorized);
        return new User(account.id, account.username, account.role);
    }
    public void logout(String token) { sessions.deleteById(hash(token)); }
    public static String hash(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch (Exception e) { throw new IllegalStateException(e); }
    }
    private String normalize(String name) {
        String value = name.strip().toLowerCase(Locale.ROOT);
        if (!value.matches("[a-z0-9_-]{3,32}")) throw new ApiException(400, "INVALID_USERNAME", "用户名需为3—32位字母、数字、下划线或短横线");
        return value;
    }
    private void checkPassword(String password) {
        if (password.length() < 8 || password.getBytes(StandardCharsets.UTF_8).length > 72)
            throw new ApiException(400, "INVALID_PASSWORD", "密码至少8个字符，UTF-8编码后不超过72字节");
    }
    private ApiException duplicate() { return new ApiException(409, "USERNAME_TAKEN", "用户名已被注册"); }
    private ApiException wrongCredentials() { return new ApiException(401, "INVALID_CREDENTIALS", "用户名或密码错误"); }
    private ApiException unauthorized() { return new ApiException(401, "UNAUTHORIZED", "请登录，或重新登录已过期的会话"); }
}
