package course.kaoyan.catalog;

import course.kaoyan.pojo.entity.practice.QuestionVersion;
import course.kaoyan.practice.PracticeAttemptRepository;
import course.kaoyan.practice.PracticeSessionItemRepository;
import java.util.HashMap;
import java.util.Map;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/** Transitional demo/legacy snapshot initialization; not a replacement for Issue #5 migrations. */
@Component
@Order(1)
public class QuestionVersionBootstrap implements ApplicationRunner {
    private final QuestionRepository questions;
    private final QuestionVersionRepository versions;
    private final QuestionVersionStore store;
    private final PracticeSessionItemRepository items;
    private final PracticeAttemptRepository attempts;

    public QuestionVersionBootstrap(QuestionRepository questions, QuestionVersionRepository versions,
            QuestionVersionStore store, PracticeSessionItemRepository items, PracticeAttemptRepository attempts) {
        this.questions = questions; this.versions = versions; this.store = store;
        this.items = items; this.attempts = attempts;
    }

    @Override @Transactional
    public void run(ApplicationArguments args) {
        var current = questions.findAll();
        Map<String, String> owners = new HashMap<>();
        for (QuestionVersion version : versions.findAll()) owners.put(version.getId(), version.getQuestionId());
        for (var q : current) {
            String existingOwner = owners.putIfAbsent(q.versionId, q.id);
            if (existingOwner != null && !existingOwner.equals(q.id))
                throw new IllegalStateException("题目版本编号属于其他题目：" + q.versionId);
        }
        // Missing historical content cannot be reconstructed from today's answer.
        for (var item : items.findAll()) check(owners, item.questionId, item.questionVersionId);
        for (var attempt : attempts.findAll()) check(owners, attempt.questionId, attempt.questionVersionId);
        for (var q : current) store.record(q);
    }

    private static void check(Map<String, String> owners, String questionId, String versionId) {
        if (!questionId.equals(owners.get(versionId)))
            throw new IllegalStateException("历史题目版本缺失或关系错误，请恢复原始内容后再启动：" + versionId);
    }
}
