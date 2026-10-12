package course.kaoyan.task;

import course.kaoyan.pojo.entity.task.Task;

import java.time.Instant;
import java.util.Optional;
import org.springframework.data.domain.*;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TaskRepository extends JpaRepository<Task, String> {
    Page<Task> findByOwnerIdAndTaskTypeOrderByCreatedAtDesc(String ownerId, String taskType, Pageable pageable);
    Page<Task> findByOwnerIdOrderByCreatedAtDesc(String ownerId, Pageable pageable);
    Optional<Task> findByIdAndOwnerId(String id, String ownerId);
    long countByOwnerIdAndCreatedAtAfter(String ownerId, Instant since);
    java.util.List<Task> findByStatus(String status);
}

