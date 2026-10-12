package course.kaoyan.task;

import com.fasterxml.jackson.databind.ObjectMapper;
import course.kaoyan.shared.ApiException;
import course.kaoyan.shared.DomainTypes.TaskType;
import course.kaoyan.shared.DomainTypes.Subject;
import java.time.*;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Service;
import org.springframework.data.domain.PageRequest;

@Service
public class TaskService implements ApplicationRunner {
    private static final Logger log = LoggerFactory.getLogger(TaskService.class);
    private final TaskRepository tasks;
    private final AgentClient agent;
    private final ObjectMapper mapper;
    private final int dailyLimit;
    private final int minuteLimit;
    public TaskService(TaskRepository tasks, AgentClient agent, ObjectMapper mapper, @Value("${agent.daily-task-limit}") int dailyLimit,
                       @Value("${agent.minute-task-limit}") int minuteLimit) {
        this.tasks = tasks; this.agent = agent; this.mapper = mapper; this.dailyLimit = dailyLimit; this.minuteLimit = minuteLimit;
    }
    public record View(String id, String input, String status, Instant createdAt, Instant finishedAt, AgentClient.Result result, String taskType, int resultSchemaVersion) {}
    public record History(List<View> items, int page, int totalPages, long totalItems) {}
    public View create(String owner, String input) { return create(owner, input, TaskType.knowledge_qa, null); }
    public View create(String owner, String input, TaskType type, Subject subject) {
        Task task;
        // 单 Java 实例的限额检查与记录创建串行；外部模型调用在锁外，且不占数据库事务。
        synchronized (this) {
            Instant start = LocalDate.now(ZoneOffset.UTC).atStartOfDay().toInstant(ZoneOffset.UTC);
            if (tasks.countByOwnerIdAndCreatedAtAfter(owner, start) >= dailyLimit)
                throw new ApiException(429, "DAILY_LIMIT", "今日任务次数已达上限，请明日再试");
            if (tasks.countByOwnerIdAndCreatedAtAfter(owner, Instant.now().minusSeconds(60)) >= minuteLimit)
                throw new ApiException(429, "RATE_LIMIT", "提交过于频繁，请稍后再试");
            task = new Task(owner, input.strip());
            task.taskType = type.name(); task.subject = subject == null ? null : subject.name();
            task = tasks.saveAndFlush(task);
        }
        log.info("task={} status=running", task.id);
        AgentClient.Result result;
        try { result = agent.run(task.id, task.input, type, subject); }
        catch (Exception e) {
            log.warn("task={} agentFailure={}", task.id, e.getClass().getSimpleName());
            result = failure(task.id, "Agent 暂时不可用或响应格式异常，请稍后新建任务重试");
        }
        task.status = result.status(); task.finishedAt = Instant.now();
        try { task.resultJson = mapper.writeValueAsString(result); }
        catch (Exception e) { throw new IllegalStateException("任务结果序列化失败", e); }
        tasks.saveAndFlush(task);
        log.info("task={} status={}", task.id, task.status);
        return view(task);
    }
    public View get(String owner, String id) {
        return view(tasks.findByIdAndOwnerId(id, owner).orElseThrow(() -> new ApiException(404, "NOT_FOUND", "任务不存在或无权访问")));
    }
    public History history(String owner, int page) { return history(owner, page, null); }
    public History history(String owner, int page, TaskType type) {
        if (page < 0 || page > 10000) throw new ApiException(400, "INVALID_PAGE", "页码不合法");
        var result = type == null ? tasks.findByOwnerIdOrderByCreatedAtDesc(owner, PageRequest.of(page, 20))
            : tasks.findByOwnerIdAndTaskTypeOrderByCreatedAtDesc(owner, type.name(), PageRequest.of(page, 20));
        return new History(result.stream().map(this::view).toList(), page, result.getTotalPages(), result.getTotalElements());
    }
    private View view(Task task) {
        try { return new View(task.id, task.input, task.status, task.createdAt, task.finishedAt,
            task.resultJson == null ? null : mapper.readValue(task.resultJson, AgentClient.Result.class), task.taskType, task.resultSchemaVersion); }
        catch (Exception e) { throw new IllegalStateException("任务记录读取失败", e); }
    }
    private AgentClient.Result failure(String id, String message) {
        return new AgentClient.Result(id, "failed", "unknown", message, List.of(), List.of(), List.of(), 0);
    }
    @Override public void run(ApplicationArguments args) throws Exception {
        // 当前只支持一个 Java 实例；重启后把中断的同步任务标为失败，不伪造完成结果。
        for (Task task : tasks.findByStatus("running")) {
            task.status = "failed"; task.finishedAt = Instant.now();
            task.resultJson = mapper.writeValueAsString(failure(task.id, "服务重启导致任务中断，请重新提交"));
            tasks.save(task);
        }
    }
}
