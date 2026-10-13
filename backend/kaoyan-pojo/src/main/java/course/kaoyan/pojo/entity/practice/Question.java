package course.kaoyan.pojo.entity.practice;

import jakarta.persistence.*;
import java.util.UUID;

@Entity
@Table(name = "questions", indexes = {
    @Index(name = "questions_active_order", columnList = "active,stableOrder"),
    @Index(name = "questions_subject", columnList = "subject")
})
public class Question {
    @Id public String id = UUID.randomUUID().toString();
    @Column(nullable = false, unique = true) public String versionId = UUID.randomUUID().toString();
    @Column(nullable = false, length = 32) public String subject;
    @Column(nullable = false, length = 16) public String difficulty;
    @Column(nullable = false) public String knowledgePointId;
    @Column(nullable = false, length = 100) public String knowledgePointName;
    @Column(nullable = false, length = 2000) public String stem;
    @Column(nullable = false, length = 1000) public String optionA;
    @Column(nullable = false, length = 1000) public String optionB;
    @Column(nullable = false, length = 1000) public String optionC;
    @Column(nullable = false, length = 1000) public String optionD;
    @Column(nullable = false, length = 4) public String correctOption;
    @Column(nullable = false, length = 4000) public String explanation;
    @Column(length = 2000) public String hintConcept;
    @Column(length = 2000) public String hintApproach;
    @Column(nullable = false, length = 200) public String sourceTitle;
    @Column(nullable = false, length = 500) public String sourceUrl;
    @Column(nullable = false, length = 100) public String sourceLocator;
    @Column(nullable = false, length = 50) public String releaseId = "practice-demo-v1";
    @Column(nullable = false) public boolean active = true;
    @Column(nullable = false) public int stableOrder;

    protected Question() {}

    public Question(String id, String versionId, String subject, String difficulty,
            String knowledgePointId, String knowledgePointName, String stem,
            String optionA, String optionB, String optionC, String optionD,
            String correctOption, String explanation, String hintConcept,
            String hintApproach, String sourceTitle, String sourceUrl,
            String sourceLocator, int stableOrder) {
        this.id = id; this.versionId = versionId; this.subject = subject;
        this.difficulty = difficulty; this.knowledgePointId = knowledgePointId;
        this.knowledgePointName = knowledgePointName; this.stem = stem;
        this.optionA = optionA; this.optionB = optionB; this.optionC = optionC;
        this.optionD = optionD; this.correctOption = correctOption;
        this.explanation = explanation; this.hintConcept = hintConcept;
        this.hintApproach = hintApproach; this.sourceTitle = sourceTitle;
        this.sourceUrl = sourceUrl; this.sourceLocator = sourceLocator;
        this.stableOrder = stableOrder;
    }
}
