package course.kaoyan.practice;

import course.kaoyan.pojo.entity.practice.PracticeAttempt;
import java.time.Instant;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.data.jpa.repository.JpaRepository;

public interface PracticeAttemptRepository extends JpaRepository<PracticeAttempt, String> {
    Optional<PracticeAttempt> findByIdAndOwnerId(String id, String ownerId);
    Optional<PracticeAttempt> findByOwnerIdAndClientRequestId(String ownerId, String clientRequestId);
    Page<PracticeAttempt> findByOwnerIdOrderByCreatedAtDesc(String ownerId, Pageable pageable);
    List<PracticeAttempt> findByOwnerIdAndGradingStatusOrderByCreatedAtAsc(String ownerId, String gradingStatus);
    List<PracticeAttempt> findByOwnerIdAndGradingStatusAndCreatedAtBetweenOrderByCreatedAtAsc(
        String ownerId, String gradingStatus, Instant from, Instant to);
}
