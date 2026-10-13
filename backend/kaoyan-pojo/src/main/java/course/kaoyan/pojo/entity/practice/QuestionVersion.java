package course.kaoyan.pojo.entity.practice;

import jakarta.persistence.*;
import java.util.Arrays;
import java.util.List;

/** Append-only content snapshot. Never serialize this entity to a student response. */
@Entity
@Table(name = "question_versions", indexes = @Index(name = "version_question", columnList = "questionId"))
public class QuestionVersion {
    @Id private String id;
    @Column(nullable = false, updatable = false) private String questionId;
    @Column(nullable = false, updatable = false, length = 32) private String subject;
    @Column(nullable = false, updatable = false, length = 16) private String difficulty;
    @Column(nullable = false, updatable = false) private String knowledgePointId;
    @Column(nullable = false, updatable = false, length = 100) private String knowledgePointName;
    @Column(nullable = false, updatable = false, length = 2000) private String stem;
    @Column(nullable = false, updatable = false, length = 1000) private String optionA;
    @Column(nullable = false, updatable = false, length = 1000) private String optionB;
    @Column(nullable = false, updatable = false, length = 1000) private String optionC;
    @Column(nullable = false, updatable = false, length = 1000) private String optionD;
    @Column(nullable = false, updatable = false, length = 4) private String correctOption;
    @Column(nullable = false, updatable = false, length = 4000) private String explanation;
    @Column(updatable = false, length = 2000) private String hintConcept;
    @Column(updatable = false, length = 2000) private String hintApproach;
    @Column(nullable = false, updatable = false, length = 200) private String sourceTitle;
    @Column(nullable = false, updatable = false, length = 500) private String sourceUrl;
    @Column(nullable = false, updatable = false, length = 100) private String sourceLocator;

    protected QuestionVersion() {}

    public QuestionVersion(Question q) {
        id = q.versionId; questionId = q.id; subject = q.subject; difficulty = q.difficulty;
        knowledgePointId = q.knowledgePointId; knowledgePointName = q.knowledgePointName;
        stem = q.stem; optionA = q.optionA; optionB = q.optionB; optionC = q.optionC; optionD = q.optionD;
        correctOption = q.correctOption; explanation = q.explanation;
        hintConcept = q.hintConcept; hintApproach = q.hintApproach;
        sourceTitle = q.sourceTitle; sourceUrl = q.sourceUrl; sourceLocator = q.sourceLocator;
    }

    public String getId() { return id; }
    public String getQuestionId() { return questionId; }

    /** Detached content copy for existing DTO mapping; never save it as the current Question. */
    public Question content() {
        return new Question(questionId, id, subject, difficulty, knowledgePointId, knowledgePointName,
            stem, optionA, optionB, optionC, optionD, correctOption, explanation, hintConcept, hintApproach,
            sourceTitle, sourceUrl, sourceLocator, 0);
    }

    public boolean matches(Question question) { return fields(content()).equals(fields(question)); }

    private static List<String> fields(Question q) {
        return Arrays.asList(q.id, q.versionId, q.subject, q.difficulty, q.knowledgePointId,
            q.knowledgePointName, q.stem, q.optionA, q.optionB, q.optionC, q.optionD, q.correctOption,
            q.explanation, q.hintConcept, q.hintApproach, q.sourceTitle, q.sourceUrl, q.sourceLocator);
    }

    @PreUpdate @PreRemove
    private void rejectMutation() { throw new IllegalStateException("题目历史版本不能覆盖或删除"); }
}
