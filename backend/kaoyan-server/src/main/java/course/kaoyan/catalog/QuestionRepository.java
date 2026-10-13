package course.kaoyan.catalog;

import course.kaoyan.pojo.entity.practice.Question;
import java.util.*;
import org.springframework.data.jpa.repository.JpaRepository;

public interface QuestionRepository extends JpaRepository<Question, String> {
    List<Question> findByActiveTrueOrderByStableOrderAsc();
    Optional<Question> findByIdAndActiveTrue(String id);
}
