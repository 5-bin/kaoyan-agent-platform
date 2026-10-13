package course.kaoyan.practice;

import course.kaoyan.pojo.entity.practice.QuestionFavorite;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.data.jpa.repository.JpaRepository;

public interface QuestionFavoriteRepository extends JpaRepository<QuestionFavorite, String> {
    Optional<QuestionFavorite> findByOwnerIdAndQuestionId(String ownerId, String questionId);
    boolean existsByOwnerIdAndQuestionId(String ownerId, String questionId);
    Page<QuestionFavorite> findByOwnerIdOrderByCreatedAtDesc(String ownerId, Pageable pageable);
    List<QuestionFavorite> findByOwnerIdOrderByCreatedAtDesc(String ownerId);
}
