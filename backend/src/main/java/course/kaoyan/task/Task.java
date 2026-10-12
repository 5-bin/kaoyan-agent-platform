package course.kaoyan.task;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name="agent_tasks", indexes=@Index(name="tasks_owner_created", columnList="ownerId,createdAt"))
public class Task {
    @Id public String id = UUID.randomUUID().toString();
    @Column(nullable=false) public String ownerId;
    @Column(nullable=false, length=8000) public String input;
    @Column(nullable=false, length=32) public String taskType = "knowledge_qa";
    public String subject;
    @Column(nullable=false) public int resultSchemaVersion = 2;
    @Column(nullable=false) public String status = "running";
    @Column(nullable=false) public Instant createdAt = Instant.now();
    public Instant finishedAt;
    @Column(columnDefinition="TEXT") public String resultJson;
    protected Task() {}
    public Task(String ownerId, String input) { this.ownerId = ownerId; this.input = input; }
}
