package course.kaoyan.pojo.entity.practice;

import jakarta.persistence.*;
import java.util.UUID;

@Entity
@Table(name = "practice_session_items", uniqueConstraints = {
    @UniqueConstraint(name = "session_item_ordinal", columnNames = {"sessionId", "ordinal"}),
    @UniqueConstraint(name = "session_item_attempt", columnNames = {"attemptId"})
}, indexes = @Index(name = "items_session", columnList = "sessionId"))
public class PracticeSessionItem {
    @Id public String id = UUID.randomUUID().toString();
    @Column(nullable = false) public String sessionId;
    @Column(nullable = false) public int ordinal;
    @Column(nullable = false) public String questionId;
    @Column(nullable = false) public String questionVersionId;
    @Column(length = 16) public String selectedOptionDraft;
    @Column(nullable = false) public int hintLevelUsed = 0;
    public String attemptId;
    @Column(nullable = false, length = 16) public String availability = "available";

    protected PracticeSessionItem() {}
    public PracticeSessionItem(String sessionId, int ordinal, String questionId, String questionVersionId) {
        this.sessionId = sessionId; this.ordinal = ordinal;
        this.questionId = questionId; this.questionVersionId = questionVersionId;
    }
}
