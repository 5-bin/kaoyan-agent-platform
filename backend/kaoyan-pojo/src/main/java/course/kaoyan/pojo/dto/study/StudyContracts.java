package course.kaoyan.pojo.dto.study;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import course.kaoyan.common.enums.DomainTypes.*;
/** 首批入参契约，完整领域字段在后续业务实现时扩展。 */
public final class StudyContracts {
    private StudyContracts() {}

    public record Summary(long validAttempts, long uniqueQuestions, Double accuracy, Double independentAccuracy) {}
}


