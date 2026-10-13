package course.kaoyan.catalog;

import course.kaoyan.common.enums.DomainTypes.*;
import course.kaoyan.common.exception.*;
import course.kaoyan.pojo.dto.catalog.CatalogContracts;
import course.kaoyan.pojo.entity.practice.Question;
import java.util.*;
import org.springframework.stereotype.Service;

@Service
public class CatalogService {
    private final QuestionRepository questions;
    public CatalogService(QuestionRepository questions) { this.questions = questions; }

    public List<CatalogContracts.KnowledgePointView> knowledgePoints(Subject subject) {
        Map<String, CatalogContracts.KnowledgePointView> result = new LinkedHashMap<>();
        for (Question q : questions.findByActiveTrueOrderByStableOrderAsc()) {
            if (subject != null && !q.subject.equals(subject.name())) continue;
            result.putIfAbsent(q.knowledgePointId, new CatalogContracts.KnowledgePointView(
                UUID.fromString(q.knowledgePointId), Subject.valueOf(q.subject), q.knowledgePointName));
        }
        return List.copyOf(result.values());
    }
    public CatalogContracts.QuestionPage questions(Subject subject, UUID knowledgePointId, Difficulty difficulty, int page) {
        if (page < 0 || page > 10000) throw new ApiException(400, "INVALID_PAGE", "页码不合法");
        List<CatalogContracts.QuestionView> filtered = questions.findByActiveTrueOrderByStableOrderAsc().stream()
            .filter(q -> subject == null || q.subject.equals(subject.name()))
            .filter(q -> knowledgePointId == null || q.knowledgePointId.equals(knowledgePointId.toString()))
            .filter(q -> difficulty == null || q.difficulty.equals(difficulty.name()))
            .map(this::view).toList();
        int from = Math.min(page * 20, filtered.size()), to = Math.min(from + 20, filtered.size());
        int totalPages = filtered.isEmpty() ? 0 : (filtered.size() + 19) / 20;
        return new CatalogContracts.QuestionPage(filtered.subList(from, to), page, totalPages, filtered.size());
    }
    public CatalogContracts.QuestionView question(UUID id) {
        return view(questions.findByIdAndActiveTrue(id.toString())
            .orElseThrow(() -> new ApiException(404, "NOT_FOUND", "题目不存在或已撤回")));
    }
    public Object source(String id) { throw PendingFeature.error("Knowledge source"); }
    public Object admissions() { throw PendingFeature.error("Admissions"); }
    public Object admission(UUID id) { throw PendingFeature.error("Admissions"); }

    private CatalogContracts.QuestionView view(Question q) {
        return new CatalogContracts.QuestionView(UUID.fromString(q.id), UUID.fromString(q.versionId),
            Subject.valueOf(q.subject), q.stem, options(q), List.of(q.knowledgePointId), Difficulty.valueOf(q.difficulty));
    }
    public static Map<String,String> options(Question q) {
        Map<String,String> result = new LinkedHashMap<>();
        result.put("A", q.optionA); result.put("B", q.optionB);
        result.put("C", q.optionC); result.put("D", q.optionD);
        return result;
    }
}

