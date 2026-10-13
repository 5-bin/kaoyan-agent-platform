package course.kaoyan.pojo.dto.practice;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import course.kaoyan.common.enums.DomainTypes.*;
public final class PracticeContracts {
    private PracticeContracts() {}

    public record SessionInput(@NotNull PracticeMode mode, Subject subject, UUID knowledgePointId,
            Difficulty difficulty, @Min(1) @Max(50) Integer questionCount) {
        public SessionInput { if (questionCount == null) questionCount = 10; }
    }
    public record AttemptInput(@NotNull UUID questionId, @NotNull UUID questionVersionId,
            @NotBlank @Pattern(regexp="[A-D]") String selectedOption, @NotNull UUID clientRequestId,
            UUID sessionId, UUID sessionItemId) {
        @AssertTrue public boolean isSessionPairValid() { return (sessionId == null) == (sessionItemId == null); }
    }
    public record Draft(@NotNull UUID itemId, @Pattern(regexp="[A-D]") String selectedOption) {}
    public record ProgressInput(@NotNull @Min(0) Long expectedRevision, @NotNull @Min(1) Integer currentOrdinal,
            @NotNull @Size(max=50) List<@Valid Draft> drafts) {}
    public record HintInput(@NotNull @Min(1) @Max(2) Integer level) {}
    public record SessionItemView(UUID id, int ordinal, UUID questionId, boolean submitted,
            String selectedOptionDraft, Boolean correct, int hintLevelUsed, String availability) {}
    public record SessionView(UUID id, PracticeMode mode, PracticeStatus status, int requestedCount,
            int actualCount, int currentOrdinal, long revision, Subject subject, UUID knowledgePointId,
            Difficulty difficulty, String releaseId, java.time.Instant createdAt, java.time.Instant finishedAt,
            List<SessionItemView> items) {}
    public record SessionPage(List<SessionView> items, int page, int totalPages, long totalItems) {}
    public record ItemView(UUID id, int ordinal, UUID questionId, UUID questionVersionId, Subject subject,
            Difficulty difficulty, String knowledgePointName, String stem, Map<String,String> options,
            String selectedOptionDraft, boolean submitted, String selectedOption, Boolean correct,
            String explanation, String sourceTitle, String sourceUrl, String sourceLocator,
            int hintLevelUsed, boolean favorite) {}
    public record HintView(int level, boolean available, String content, int hintLevelUsed) {}
    public record AttemptView(UUID id, UUID questionId, UUID questionVersionId, String selectedOption,
            boolean correct, int hintLevelUsed, java.time.Instant createdAt, String explanation,
            String sourceTitle, String sourceUrl, String sourceLocator, UUID sessionId, UUID sessionItemId) {}
    public record AttemptPage(List<AttemptView> items, int page, int totalPages, long totalItems) {}
    public record WrongView(UUID id, UUID questionId, String stem, Subject subject, String knowledgePointName,
            int wrongCount, int consecutiveCorrect, WrongStatus status, java.time.Instant updatedAt,
            UUID latestAttemptId) {}
    public record WrongPage(List<WrongView> items, int page, int totalPages, long totalItems) {}
    public record FavoriteView(UUID questionId, String stem, Subject subject, String knowledgePointName,
            boolean available, java.time.Instant createdAt) {}
    public record FavoritePage(List<FavoriteView> items, int page, int totalPages, long totalItems) {}
    public record SessionResult(UUID sessionId, int actualCount, int answered, int unanswered,
            int correct, int wrong, int hintsUsed, Double accuracy, Double independentAccuracy) {}
    public record FavoriteState(UUID questionId, boolean favorite) {}
}


