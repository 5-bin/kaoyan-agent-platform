package course.kaoyan.pojo.entity.practice;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "question_favorites", uniqueConstraints = @UniqueConstraint(name = "favorite_owner_question", columnNames = {"ownerId", "questionId"}),
    indexes = @Index(name = "favorite_owner_created", columnList = "ownerId,createdAt"))
public class QuestionFavorite {
    @Id public String id = UUID.randomUUID().toString();
    @Column(nullable = false) public String ownerId;
    @Column(nullable = false) public String questionId;
    @Column(nullable = false) public Instant createdAt = Instant.now();

    protected QuestionFavorite() {}
    public QuestionFavorite(String ownerId, String questionId) { this.ownerId = ownerId; this.questionId = questionId; }
}
