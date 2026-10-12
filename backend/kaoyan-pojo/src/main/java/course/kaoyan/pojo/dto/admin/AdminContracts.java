package course.kaoyan.pojo.dto.admin;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import course.kaoyan.common.enums.DomainTypes.*;
/** 首批入参契约，完整领域字段在后续业务实现时扩展。 */
public final class AdminContracts {
    private AdminContracts() {}

    public record DocumentInput(@NotBlank @Size(max=200) String title, @NotBlank @Size(max=2000) String url,
            @NotBlank @Size(max=200) String locator, @NotBlank @Size(max=100) String version,
            @NotBlank @Size(max=50000) String content, @NotBlank @Size(max=1000) String license) {}
    public record AdmissionInput(@NotBlank String schoolCode, @NotBlank String schoolName,
            @NotBlank String collegeCode, @NotBlank String collegeName, @NotBlank String majorCode,
            @NotBlank String majorName, @NotNull DegreeType degreeType, @NotBlank String studyMode,
            @NotNull @Min(2000) @Max(2100) Integer examYear, @NotEmpty List<String> sourceChunkIds) {}
    public record QuestionInput(@NotNull Subject subject, @NotEmpty List<String> knowledgePointIds,
            @NotNull Difficulty difficulty, @NotBlank @Size(max=10000) String stem,
            @NotEmpty Map<String,String> options, @NotBlank String correctOption,
            @NotBlank String explanation, @NotEmpty List<String> sourceChunkIds) {}
    public record ReviewInput(@NotNull ReviewStatus status, @Size(max=2000) String comment) {}
}


