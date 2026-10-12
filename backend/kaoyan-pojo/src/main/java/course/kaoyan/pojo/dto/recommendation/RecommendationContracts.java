package course.kaoyan.pojo.dto.recommendation;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import course.kaoyan.common.enums.DomainTypes.*;
/** 首批入参契约，完整领域字段在后续业务实现时扩展。 */
public final class RecommendationContracts {
    private RecommendationContracts() {}

    public record Candidate(UUID programId, int rank, List<String> matchedConditions, List<String> pendingChecks, List<String> sourceIds) {}
}


