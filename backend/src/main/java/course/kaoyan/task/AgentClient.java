package course.kaoyan.task;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class AgentClient {
    private final RestClient client;
    private static final String RELEASE = "demo-408-v1";
    public record Source(String id, String title, String url, String locator, String version, String excerpt, String retrievedAt) {}
    public record Result(String taskId, String status, String mode, String answer, List<String> steps,
                         List<Source> sources, List<String> followUp, long latencyMs, String releaseId, Map<String, Object> data) {
        public Result { if (data == null) data = Map.of(); }
        public Result(String taskId, String status, String mode, String answer, List<String> steps,
                      List<Source> sources, List<String> followUp, long latencyMs) {
            this(taskId, status, mode, answer, steps, sources, followUp, latencyMs, RELEASE, Map.of());
        }
    }
    @Autowired
    public AgentClient(@Value("${agent.base-url}") String baseUrl, @Value("${agent.internal-key}") String key,
                       @Value("${agent.timeout-seconds}") int timeout) {
        if (key.length() < 16 || !key.chars().allMatch(c -> c < 128)) throw new IllegalStateException("AGENT_INTERNAL_KEY 需至少16位ASCII字符，Java/Python需一致");
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(3)); factory.setReadTimeout(Duration.ofSeconds(timeout));
        client = RestClient.builder().baseUrl(baseUrl).requestFactory(factory).defaultHeader("X-Internal-Key", key).build();
    }
    AgentClient(RestClient client) { this.client = client; }
    public Result run(String id, String input) {
        return run(id, input, course.kaoyan.shared.DomainTypes.TaskType.knowledge_qa, null);
    }
    public Result run(String id, String input, course.kaoyan.shared.DomainTypes.TaskType type,
                      course.kaoyan.shared.DomainTypes.Subject subject) {
        Map<String, Object> context = subject == null ? Map.of() : Map.of("subject", subject.name());
        Result result = client.post().uri("/internal/run").body(Map.of("taskId", id, "input", input,
            "taskType", type.name(), "releaseId", RELEASE, "context", context)).retrieve().body(Result.class);
        if (result == null || !id.equals(result.taskId()) || !List.of("completed", "needs_input", "unsupported", "failed").contains(result.status())
            || !List.of("demo", "model").contains(result.mode()) || result.answer() == null || result.answer().length() > 20000
            || result.steps() == null || result.sources() == null || result.followUp() == null
            || result.latencyMs() < 0 || !RELEASE.equals(result.releaseId()))
            throw new IllegalStateException("Agent 返回不符合契约");
        return result;
    }
}
