package course.kaoyan.profile;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import course.kaoyan.shared.DomainTypes.*;
/** 首批入参契约，完整领域字段在后续业务实现时扩展。 */
public final class ProfileContracts {
    private ProfileContracts() {}

    public record Input(@Min(2000) @Max(2100) Integer examYear, @Size(max=30) List<String> targetMajorCodes,
        DegreeType degreeType, @Size(max=30) List<String> regions, RegionConstraint regionConstraint,
        @Size(max=80) String studyMode, @Size(max=10) List<String> examSubjects,
        @Size(max=2000) String foundation, Map<String, Integer> estimatedScores) {}
}
