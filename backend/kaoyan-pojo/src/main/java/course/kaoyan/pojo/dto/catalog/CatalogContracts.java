package course.kaoyan.pojo.dto.catalog;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import course.kaoyan.common.enums.DomainTypes.*;
/** 首批入参契约，完整领域字段在后续业务实现时扩展。 */
public final class CatalogContracts {
    private CatalogContracts() {}

    public record QuestionView(UUID id, UUID questionVersionId, Subject subject, String stem,
        Map<String, String> options, List<String> knowledgePointIds, Difficulty difficulty) {}
}


