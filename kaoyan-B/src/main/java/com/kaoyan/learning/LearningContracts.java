package com.kaoyan.learning;

import jakarta.validation.constraints.*;
import java.util.*;

/** Public DTOs; owners, grading snapshots and model grants are never request fields. */
public final class LearningContracts {
    private LearningContracts() {}
    public record Progress(@NotNull @Min(0) Integer revision, @NotNull @Min(0) Integer currentIndex,
            @NotNull @Size(max=50) Map<@Positive Long, @Pattern(regexp="[A-D]|") String> answers) {}
    public record Hint(@Min(1) @Max(2) int level) {}
    public record Submit(@NotNull @Positive Long questionId, @Positive Long itemId,
            @NotBlank @Size(max=64) String clientRequestId, @NotBlank @Pattern(regexp="[A-Da-d]") String answer) {}
    public record Settings(@NotNull @Min(0) Integer revision, boolean enabled,
            @NotNull Map<String,Object> preferences) {}
    public record Blueprint(@NotBlank @Pattern(regexp="[A-Za-z0-9_-]{1,64}") String id,
            @Min(1) int version, @NotEmpty @Size(max=200) List<@jakarta.validation.Valid Cell> cells) {}
    public record Cell(@NotBlank @Size(max=50) String subject, @NotBlank @Size(max=255) String knowledgePoint,
            @NotBlank @Size(max=100) String knowledgePointId,
            @NotBlank @Pattern(regexp="EASY|MEDIUM|HARD") String difficulty, @Positive @Max(50) int count,
            @DecimalMin(value="0",inclusive=false) @DecimalMax("1") double weight) {}
    public record Revision(@NotNull @jakarta.validation.Valid com.kaoyan.dto.request.QuestionUpdateRequest replacement,
            @NotNull @jakarta.validation.Valid Hints hints, @NotBlank @Size(max=2000) String reviewComment) {}
    public record Withdraw(@NotBlank @Size(max=2000) String reason) {}
    public record Hints(@Size(max=2000) String concept, @Size(max=2000) String direction) {}
    public record Metric(@NotBlank @Size(max=100) String programId, @NotBlank @Size(max=255) String school,
            @NotBlank @Size(max=255) String college, @NotBlank @Pattern(regexp="[0-9]{6}") String majorCode,
            @Min(2000) @Max(2100) int year,
            @NotBlank @Pattern(regexp="TOTAL_CUTOFF|SUBJECT_CUTOFF|ADMISSION_MIN|ADMISSION_MEAN") String metricType,
            @Pattern(regexp="[0-9]{3}") String examSubject, @Min(1) @Max(500) int maxScore,
            @NotNull @DecimalMin("0") Double score, @NotNull Map<String,Object> source) {}
    public record Item(long itemId, long questionId, int orderIndex, String subject, String knowledgePoint,
            String difficulty, String content, String optionA, String optionB, String optionC, String optionD,
            String userAnswer, String draftAnswer, boolean submitted, int hintLevelUsed, boolean withdrawn,
            Integer isCorrect, String answer, String analysis) {}
    public record State(String sessionId, String kind, String state, int revision, int currentIndex,
            Map<String,Object> blueprint, List<Item> items) {}
    public record Submission(long questionId, long itemId, String userAnswer, boolean submitted,
            Integer isCorrect, String answer, String analysis) {}
    public record Group(String knowledgePointId, String subject, String knowledgePoint, String difficulty,
            int samples, int correct, int assisted, int unknown, Double masteryIndex,
            String sampleStatus, double weight, Double priority, boolean anomaly) {}
    public record Profile(int revision, String algorithmVersion, String blueprintVersion, Double referenceScore,
            double coverage, int independentSamples, int assistedSamples, int unknownSamples,
            boolean sufficient, String status, String updatedAt, List<Group> groups, List<String> notices) {}
}
