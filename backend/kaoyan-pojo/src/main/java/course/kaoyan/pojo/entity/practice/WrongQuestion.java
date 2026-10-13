package course.kaoyan.pojo.entity.practice;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "wrong_questions", uniqueConstraints = @UniqueConstraint(name = "wrong_owner_question", columnNames = {"ownerId", "questionId"}),
    indexes = @Index(name = "wrong_owner_status", columnList = "ownerId,status"))
public class WrongQuestion {
    @Id public String id = UUID.randomUUID().toString();
    @Column(nullable = false) public String ownerId;
    @Column(nullable = false) public String questionId;
    @Column(nullable = false) public String latestAttemptId;
    @Column(nullable = false) public int wrongCount = 0;
    @Column(nullable = false) public int consecutiveCorrect = 0;
    @Column(nullable = false, length = 16) public String status = "reviewing";
    @Column(nullable = false) public Instant updatedAt = Instant.now();

    protected WrongQuestion() {}
    public WrongQuestion(String ownerId, String questionId, String latestAttemptId) {
        this.ownerId = ownerId; this.questionId = questionId; this.latestAttemptId = latestAttemptId;
    }
}
