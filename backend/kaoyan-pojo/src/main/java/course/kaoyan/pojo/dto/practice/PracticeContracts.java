package course.kaoyan.pojo.dto.practice;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import course.kaoyan.common.enums.DomainTypes.*;
/** 首批入参契约，完整领域字段在后续业务实现时扩展。 */
public final class PracticeContracts {
    private PracticeContracts() {}

    public record SessionInput(@NotNull PracticeMode mode, Subject subject, UUID knowledgePointId,
            Difficulty difficulty, @Min(1) @Max(50) Integer questionCount) {
        public SessionInput { if (questionCount == null) questionCount = 10; }
    }
    public record AttemptInput(@NotNull UUID questionId, @NotNull UUID questionVersionId,
            @NotBlank @Size(max=16) String selectedOption, @NotNull UUID clientRequestId,
            UUID sessionId, UUID sessionItemId) {
        @AssertTrue public boolean isSessionPairValid() { return (sessionId == null) == (sessionItemId == null); }
    }
    public record Draft(@NotNull UUID itemId, @Size(max=16) String selectedOption) {}
    public record ProgressInput(@NotNull @Min(0) Long expectedRevision, @NotNull @Min(1) Integer currentOrdinal,
            @NotNull @Size(max=50) List<@Valid Draft> drafts) {}
    public record HintInput(@NotNull @Min(1) @Max(2) Integer level) {}
    public record SessionView(UUID id, PracticeMode mode, PracticeStatus status, int actualCount, long revision) {}
}


