package course.kaoyan.practice;

import course.kaoyan.pojo.entity.practice.WrongQuestion;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.data.jpa.repository.JpaRepository;

public interface WrongQuestionRepository extends JpaRepository<WrongQuestion, String> {
    Optional<WrongQuestion> findByIdAndOwnerId(String id, String ownerId);
    Optional<WrongQuestion> findByOwnerIdAndQuestionId(String ownerId, String questionId);
    Page<WrongQuestion> findByOwnerIdOrderByUpdatedAtDesc(String ownerId, Pageable pageable);
    Page<WrongQuestion> findByOwnerIdAndStatusOrderByUpdatedAtDesc(String ownerId, String status, Pageable pageable);
    List<WrongQuestion> findByOwnerIdAndStatusOrderByUpdatedAtDesc(String ownerId, String status);
}
