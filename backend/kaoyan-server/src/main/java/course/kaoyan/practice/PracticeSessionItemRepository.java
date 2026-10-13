package course.kaoyan.practice;

import course.kaoyan.pojo.entity.practice.PracticeSessionItem;
import java.util.*;
import org.springframework.data.jpa.repository.JpaRepository;

public interface PracticeSessionItemRepository extends JpaRepository<PracticeSessionItem, String> {
    List<PracticeSessionItem> findBySessionIdOrderByOrdinalAsc(String sessionId);
    Optional<PracticeSessionItem> findByIdAndSessionId(String id, String sessionId);
    long countBySessionIdAndAttemptIdIsNotNull(String sessionId);
}
