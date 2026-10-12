package course.kaoyan.pojo.entity.auth;

import jakarta.persistence.*;
import java.util.UUID;

@Entity
@Table(name = "accounts")
public class Account {
    @Id public String id = UUID.randomUUID().toString();
    @Column(nullable = false, unique = true, length = 32) public String username;
    @Column(nullable = false) public String passwordHash;
    @Column(nullable = false, length = 16) public String role = "student";
    protected Account() {}
    public Account(String username, String hash) { this.username = username; this.passwordHash = hash; }
}

