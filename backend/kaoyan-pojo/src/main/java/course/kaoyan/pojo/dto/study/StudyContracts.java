package course.kaoyan.pojo.dto.study;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import course.kaoyan.common.enums.DomainTypes.*;
public final class StudyContracts {
    private StudyContracts() {}

    public record KnowledgePointStat(String knowledgePointId, String knowledgePointName,
            long attempts, long correct, Double accuracy) {}
    public record Summary(long validAttempts, long uniqueQuestions, long hintsUsed,
            Double accuracy, Double independentAccuracy, List<KnowledgePointStat> knowledgePoints) {}
}


