package course.kaoyan.catalog;

import course.kaoyan.pojo.entity.practice.QuestionVersion;
import java.util.List;
import java.util.Optional;
import org.springframework.data.repository.Repository;

/** Read-only repository; new snapshots are inserted by QuestionVersionStore. */
public interface QuestionVersionRepository extends Repository<QuestionVersion, String> {
    Optional<QuestionVersion> findById(String id);
    List<QuestionVersion> findAll();
}
