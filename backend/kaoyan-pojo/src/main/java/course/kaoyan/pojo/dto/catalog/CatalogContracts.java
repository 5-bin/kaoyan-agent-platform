package course.kaoyan.pojo.dto.catalog;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import course.kaoyan.common.enums.DomainTypes.*;
public final class CatalogContracts {
    private CatalogContracts() {}

    public record KnowledgePointView(UUID id, Subject subject, String name) {}
    public record QuestionView(UUID id, UUID questionVersionId, Subject subject, String stem,
        Map<String, String> options, List<String> knowledgePointIds, Difficulty difficulty) {}
    public record QuestionPage(List<QuestionView> items, int page, int totalPages, long totalItems) {}
}


