package course.kaoyan.pojo.entity.practice;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "practice_attempts", uniqueConstraints = {
    @UniqueConstraint(name = "attempt_owner_request", columnNames = {"ownerId", "clientRequestId"}),
    @UniqueConstraint(name = "attempt_session_item", columnNames = {"sessionItemId"})
}, indexes = @Index(name = "attempt_owner_created", columnList = "ownerId,createdAt"))
public class PracticeAttempt {
    @Id public String id = UUID.randomUUID().toString();
    @Column(nullable = false) public String ownerId;
    @Column(nullable = false) public String questionId;
    @Column(nullable = false) public String questionVersionId;
    @Column(nullable = false, length = 16) public String selectedOption;
    @Column(nullable = false) public boolean correct;
    @Column(nullable = false, length = 16) public String gradingStatus = "valid";
    @Column(nullable = false) public String clientRequestId;
    public String sessionId;
    public String sessionItemId;
    @Column(nullable = false) public int hintLevelUsed;
    @Column(nullable = false) public Instant createdAt = Instant.now();

    protected PracticeAttempt() {}
    public PracticeAttempt(String ownerId, String questionId, String questionVersionId,
            String selectedOption, boolean correct, String clientRequestId,
            String sessionId, String sessionItemId, int hintLevelUsed) {
        this.ownerId = ownerId; this.questionId = questionId;
        this.questionVersionId = questionVersionId; this.selectedOption = selectedOption;
        this.correct = correct; this.clientRequestId = clientRequestId;
        this.sessionId = sessionId; this.sessionItemId = sessionItemId;
        this.hintLevelUsed = hintLevelUsed;
    }
}
