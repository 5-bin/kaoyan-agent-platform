package course.kaoyan.auth;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "account_sessions")
public class Session {
    @Id public String tokenHash;
    @Column(nullable = false) public String accountId;
    @Column(nullable = false) public Instant expiresAt;
    protected Session() {}
    public Session(String hash, String accountId, Instant expiresAt) {
        this.tokenHash = hash; this.accountId = accountId; this.expiresAt = expiresAt;
    }
}
