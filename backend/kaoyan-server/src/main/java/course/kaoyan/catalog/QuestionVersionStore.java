package course.kaoyan.catalog;

import course.kaoyan.common.exception.ApiException;
import course.kaoyan.pojo.entity.practice.Question;
import course.kaoyan.pojo.entity.practice.QuestionVersion;
import jakarta.persistence.EntityManager;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Internal persistence only: recording a snapshot does not approve or publish a question. */
@Service
public class QuestionVersionStore {
    private final QuestionVersionRepository versions;
    private final EntityManager entityManager;

    public QuestionVersionStore(QuestionVersionRepository versions, EntityManager entityManager) {
        this.versions = versions; this.entityManager = entityManager;
    }

    @Transactional
    public void record(Question question) {
        var existing = versions.findById(question.versionId);
        if (existing.isPresent()) {
            if (!existing.get().matches(question))
                throw new ApiException(409, "QUESTION_VERSION_IMMUTABLE", "题目内容已变化，必须使用新的版本编号");
            return;
        }
        // persist, not merge: an existing version ID must never be overwritten.
        entityManager.persist(new QuestionVersion(question));
        entityManager.flush();
    }

    @Transactional(readOnly = true)
    public Question require(String questionId, String versionId) {
        return versions.findById(versionId).filter(v -> v.getQuestionId().equals(questionId))
            .map(QuestionVersion::content)
            .orElseThrow(() -> new ApiException(409, "QUESTION_VERSION_UNAVAILABLE", "题目历史版本缺失或与题目不匹配，请联系管理员"));
    }
}
