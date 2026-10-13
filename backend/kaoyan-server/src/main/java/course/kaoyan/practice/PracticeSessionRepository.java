package course.kaoyan.practice;

import course.kaoyan.pojo.entity.practice.PracticeSession;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.data.jpa.repository.JpaRepository;

public interface PracticeSessionRepository extends JpaRepository<PracticeSession, String> {
    Optional<PracticeSession> findByIdAndOwnerId(String id, String ownerId);
    Page<PracticeSession> findByOwnerIdOrderByCreatedAtDesc(String ownerId, Pageable pageable);
    Page<PracticeSession> findByOwnerIdAndStatusOrderByCreatedAtDesc(String ownerId, String status, Pageable pageable);
}
