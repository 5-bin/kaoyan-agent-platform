package course.kaoyan.pojo.entity.practice;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "practice_sessions", indexes = @Index(name = "practice_owner_created", columnList = "ownerId,createdAt"))
public class PracticeSession {
    @Id public String id = UUID.randomUUID().toString();
    @Column(nullable = false) public String ownerId;
    @Column(nullable = false, length = 16) public String mode;
    @Column(length = 32) public String subject;
    public String knowledgePointId;
    @Column(length = 16) public String difficulty;
    @Column(nullable = false) public int requestedCount;
    @Column(nullable = false) public int actualCount;
    @Column(nullable = false, length = 16) public String status = "active";
    @Column(nullable = false) public int currentOrdinal = 1;
    @Column(nullable = false) public long revision = 0;
    @Column(nullable = false, length = 50) public String releaseId = "practice-demo-v1";
    @Column(nullable = false) public Instant createdAt = Instant.now();
    public Instant finishedAt;

    protected PracticeSession() {}
    public PracticeSession(String ownerId, String mode, String subject, String knowledgePointId,
            String difficulty, int requestedCount, int actualCount) {
        this.ownerId = ownerId; this.mode = mode; this.subject = subject;
        this.knowledgePointId = knowledgePointId; this.difficulty = difficulty;
        this.requestedCount = requestedCount; this.actualCount = actualCount;
    }
}
