package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.common.ApiException;
import com.kaoyan.common.PageResult;
import com.kaoyan.config.AgentProperties;
import com.kaoyan.dto.agent.AgentRequest;
import com.kaoyan.dto.agent.AgentResponse;
import com.kaoyan.entity.*;
import com.kaoyan.feign.AgentFeignClient;
import com.kaoyan.mapper.*;
import com.kaoyan.service.TaskService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import java.net.URI;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class TaskServiceImpl extends ServiceImpl<TaskMapper, Task> implements TaskService, ApplicationRunner {
    private static final Set<String> TYPES = Set.of("KNOWLEDGE_QA", "SCHOOL_RECOMMEND", "PRACTICE_SUMMARY", "CHAT", "WRONG_QUESTION_TUTOR");
    private final AgentFeignClient agentClient;
    private final AgentProperties agentProps;
    private final UserMapper userMapper;
    private final PracticeRecordMapper practiceRecordMapper;
    private final QuestionMapper questionMapper;
    private final TaskStore store;
    private final WrongQuestionTutorContext tutorContext;
    private final com.kaoyan.service.ReferenceSourcePolicy sourcePolicy;
    @org.springframework.beans.factory.annotation.Autowired(required=false)
    private com.kaoyan.service.AssistantPrivacyService privacy;
    @org.springframework.beans.factory.annotation.Autowired(required=false)
    private org.springframework.beans.factory.ObjectProvider<com.kaoyan.service.ConversationService> conversations;

    @Override
    public Task submit(Long userId, String taskType, Map<String, Object> input) {
        if (taskType == null || !TYPES.contains(taskType)) throw new ApiException(400, "未知任务类型");
        Map<String, Object> fields = input == null ? Map.of() : input;
        Set<String> allowed = switch (taskType) {
            case "WRONG_QUESTION_TUTOR" -> Set.of("recordId", "query", "parentTaskId");
            case "PRACTICE_SUMMARY" -> Set.of("sessionId");
            case "SCHOOL_RECOMMEND", "CHAT" -> Set.of("query", "preferences", "messages");
            default -> Set.of("query", "messages");
        };
        if (!allowed.containsAll(fields.keySet())) throw new ApiException(400, "请求包含不适用的字段");
        Task task = new Task();
        task.setId(UUID.randomUUID().toString());
        task.setUserId(userId);
        task.setTaskType(taskType);
        task.setStatus("RUNNING");
        AgentRequest request = buildRequest(userId, taskType, task.getId(), fields);
        request.setQuotaExempt(store.isQuotaExempt(userId));
        Map<String,Object> consent=privacy==null?Map.of("modelAllowed",false,"scopes",List.of(),"version",0):privacy.settings(userId);
        request.setPrivacy(privacy==null?consent:privacy.wire(consent));
        Map<String,Object> grant=com.kaoyan.security.UserContext.sessionGrant();
        // Save the exact authorized context, not a client-supplied profile or owner.
        Map<String, Object> snapshot = new LinkedHashMap<>(fields);
        snapshot.put("profileSnapshot", request.getProfile());
        if (request.getQuestions() != null) snapshot.put("questions", request.getQuestions());
        if (request.getAttempt() != null) {
            snapshot.put("attempt", request.getAttempt());
            snapshot.put("messages", request.getMessages());
        }
        task.setInputPayload(snapshot);
        synchronized (store) { store.begin(task); }
        try {
            if(privacy!=null) privacy.check(userId,grant,((Number)consent.get("version")).intValue());
            if(privacy!=null && Boolean.TRUE.equals(consent.get("modelAllowed")) && !privacy.provider().equals(consent.get("provider")))
                throw new ApiException(409,"模型接收端点已变化，请重新授权");
            AgentResponse response = agentClient.chat(agentProps.getInternalKey(), request);
            validateResponse(task, response);
            sourcePolicy.validateResponse(response);
            if(privacy!=null) privacy.check(userId,grant,((Number)consent.get("version")).intValue());
            if(privacy!=null && Boolean.TRUE.equals(consent.get("modelAllowed")) && !privacy.provider().equals(consent.get("provider")))
                throw new ApiException(409,"模型接收端点已变化，请重新授权");
            task.setStatus(response.getStatus());
            task.setReleaseId(response.getReleaseId());
            if ("SUCCESS".equals(response.getStatus())) {
                Map<String, Object> result = new LinkedHashMap<>(asMap(response.getResult()));
                result.put("references", response.getReferences());
                task.setResultPayload(result);
            } else task.setErrorMessage("Agent处理失败，请稍后重试");
        } catch (Exception e) {
            log.warn("task={} agentFailure={}", task.getId(), e.getClass().getSimpleName());
            task.setStatus("FAILED");
            task.setErrorMessage("Agent暂时不可用或响应不符合契约，请按任务编号检查日志");
        }
        if(privacy!=null) privacy.finishTask(task,grant,((Number)consent.get("version")).intValue());
        else store.finish(task);
        return task;
    }

    private AgentRequest buildRequest(Long userId, String type, String id, Map<String, Object> input) {
        User user = userMapper.selectById(userId);
        if (user == null) throw new ApiException(401, "账号不存在");
        AgentRequest request = new AgentRequest();
        request.setTaskId(id);
        request.setUserId(userId);
        request.setTaskType(type);
        Map<String, Object> profile = new LinkedHashMap<>();
        profile.put("targetSchool", user.getTargetSchool());
        profile.put("targetMajor", user.getTargetMajor());
        profile.put("examYear", user.getExamYear());
        // Free-form background is unrelated to rule-based screening and never forwarded by default.
        request.setProfile(profile);
        if ("WRONG_QUESTION_TUTOR".equals(type)) {
            // This path accepts only record IDs and queries, never client-provided context.
            request.setProfile(Map.of());
            tutorContext.populate(request, userId, input);
            return request;
        }
        if (!"PRACTICE_SUMMARY".equals(type)) {
            Object query = input.get("query");
            if (!(query instanceof String text) || text.isBlank() || text.strip().length() > 8000)
                throw new ApiException(400, "问题长度需为1—8000字符");
            request.setUserInput(text.strip());
        }
        if (input.containsKey("preferences")) {
            Map<String, Object> prefs = asMap(input.get("preferences"));
            if (!Set.of("majorCodes", "degreeType", "regions", "regionConstraint", "studyMode", "examSubjects", "explainWithAi")
                    .containsAll(prefs.keySet())) throw new ApiException(400, "未知推荐偏好");
            for (Map.Entry<String, Set<String>> rule : Map.of(
                    "degreeType", Set.of("academic", "professional"), "regionConstraint", Set.of("required", "preferred"),
                    "studyMode", Set.of("full_time", "part_time")).entrySet()) {
                Object value = prefs.get(rule.getKey());
                if (value != null && !rule.getValue().contains(value)) throw new ApiException(400, "推荐偏好枚举无效");
            }
            for (String key : List.of("majorCodes", "regions", "examSubjects")) {
                Object value = prefs.get(key);
                if (value == null) continue;
                int max = key.equals("majorCodes") ? 10 : key.equals("examSubjects") ? 4 : 30;
                if (!(value instanceof List<?> list) || list.size() > max) throw new ApiException(400, "推荐条件数量不合法");
                for (Object item : list) {
                    if (!(item instanceof String text) || text.isBlank() || text.length() > 50
                            || key.equals("majorCodes") && !text.matches("[0-9]{6}")
                            || key.equals("examSubjects") && !text.matches("[0-9]{3}"))
                        throw new ApiException(400, "推荐条件格式不合法");
                }
            }
            if (prefs.containsKey("explainWithAi") && !(prefs.get("explainWithAi") instanceof Boolean))
                throw new ApiException(400, "explainWithAi需为布尔值");
            request.setPreferences(prefs);
        }
        if (input.containsKey("messages")) {
            if (!(input.get("messages") instanceof List<?> history) || history.size() > 6)
                throw new ApiException(400, "对话历史最多6条");
            for (Object item : history) {
                Map<String, Object> message = asMap(item);
                if (!message.keySet().equals(Set.of("role", "content"))
                        || !Set.of("user", "assistant").contains(message.get("role"))
                        || !(message.get("content") instanceof String content) || content.isBlank() || content.length() > 4000)
                    throw new ApiException(400, "对话历史格式不合法");
            }
            request.setMessages(new ArrayList<>(history));
        }
        if ("PRACTICE_SUMMARY".equals(type)) {
            if (!(input.get("sessionId") instanceof String session) || session.isBlank() || session.length() > 64)
                throw new ApiException(400, "缺少合法练习批次");
            List<PracticeRecord> records = practiceRecordMapper.selectList(new LambdaQueryWrapper<PracticeRecord>()
                .eq(PracticeRecord::getUserId, userId).eq(PracticeRecord::getSessionId, session)
                .orderByAsc(PracticeRecord::getOrderIndex));
            if (records.isEmpty()) throw new ApiException(404, "练习批次不存在或无权访问");
            if (records.stream().noneMatch(r -> "valid".equals(r.getGradingStatus()))
                    || records.stream().anyMatch(r -> "valid".equals(r.getGradingStatus()) && r.getIsCorrect() == null))
                throw new ApiException(409, "批次尚未完成或无有效作答，不能生成总结");
            if (records.stream().filter(r -> "valid".equals(r.getGradingStatus()))
                    .anyMatch(r -> r.getQuestionSnapshot() == null || r.getQuestionSnapshot().isEmpty()))
                throw new ApiException(409, "该批次包含缺少题目版本快照的历史作答，暂不支持生成总结");
            List<Map<String, Object>> snapshots = new ArrayList<>();
            for (PracticeRecord record : records) {
                if (record.getIsCorrect() == null || !"valid".equals(record.getGradingStatus())) continue;
                // Local display snapshots can grow; the Python contract remains unchanged.
                Map<String, Object> q = new LinkedHashMap<>();
                for (String key : List.of("id", "version", "subject", "knowledgePoint", "content", "answer", "analysis")) {
                    if (record.getQuestionSnapshot().containsKey(key)) q.put(key, record.getQuestionSnapshot().get(key));
                }
                q.put("correct", record.getIsCorrect() == 1);
                snapshots.add(q);
            }
            if (snapshots.size() > 50) throw new ApiException(400, "总结最多50题");
            request.setSessionId(session);
            request.setQuestions(snapshots);
        }
        return request;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object value) {
        if (!(value instanceof Map<?, ?> map) || map.keySet().stream().anyMatch(k -> !(k instanceof String)))
            throw new ApiException(400, "对象格式不合法");
        return (Map<String, Object>) map;
    }

    public static void validateResponse(Task task, AgentResponse response) {
        if (response == null || !task.getId().equals(response.getTaskId())
                || response.getStatus() == null || !Set.of("SUCCESS", "FAILED").contains(response.getStatus())
                || response.getReleaseId() == null || !response.getReleaseId().matches("rag-v1-[a-f0-9]{16}"))
            throw new IllegalStateException("Agent response mismatch");
        if (!"SUCCESS".equals(response.getStatus())) return;
        Map<String, Object> result = asMap(response.getResult());
        if ("WRONG_QUESTION_TUTOR".equals(task.getTaskType())) {
            Map<String, Object> attempt = asMap(task.getInputPayload().get("attempt"));
            for (String field : List.of("standardAnswer", "userAnswer", "questionVersion", "recordId")) {
                String source = field.equals("standardAnswer") ? "answer" : field.equals("questionVersion") ? "version" : field;
                if (!Objects.toString(attempt.get(source)).equals(Objects.toString(result.get(field))))
                    throw new IllegalStateException("Tutor changed authoritative result");
            }
            if (!(result.get("answer") instanceof String explanation) || explanation.isBlank() || explanation.length() > 4000
                    || !response.getReferences().isEmpty()) throw new IllegalStateException("Invalid tutor result");
        }
        if (result.get("outcome") == null || !Set.of("COMPLETED", "NEEDS_INPUT", "UNSUPPORTED").contains(result.get("outcome"))
                || !response.getReleaseId().equals(result.get("releaseId"))
                || result.get("explanationMode") == null || !Set.of("rules", "ai", "fallback").contains(result.get("explanationMode"))
                || result.get("resolvedTaskType") == null || !TYPES.contains(result.get("resolvedTaskType"))
                || (!"CHAT".equals(task.getTaskType()) && !Objects.equals(task.getTaskType(), result.get("resolvedTaskType")))
                || !(result.get("answer") instanceof String answer) || answer.length() > 20000
                || response.getReferences() == null || response.getReferences().size() > 20)
            throw new IllegalStateException("Agent result mismatch");
        Set<String> sourceIds = new HashSet<>();
        for (Object item : response.getReferences()) {
            Map<String, Object> ref = asMap(item);
            URI uri = URI.create(Objects.toString(ref.get("url"), ""));
            if (!"https".equals(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null
                    || !(ref.get("id") instanceof String sourceId) || !sourceIds.add(sourceId)
                    || !(ref.get("version") instanceof String)) throw new IllegalStateException("Invalid reference");
            for (String field : List.of("title", "locator", "version", "retrievedAt", "excerpt"))
                if (!(ref.get(field) instanceof String value) || value.isBlank() || value.length() > 4000)
                    throw new IllegalStateException("Incomplete reference");
        }
        if (result.get("candidates") instanceof List<?> candidates) {
            if (candidates.size() > 5) throw new IllegalStateException("Too many candidates");
            Set<Object> ids = new HashSet<>();
            for (Object item : candidates) {
                Map<String, Object> candidate = asMap(item);
                if (!(candidate.get("programId") instanceof String) || !ids.add(candidate.get("programId"))
                        || !(candidate.get("sourceIds") instanceof List<?> cited) || cited.isEmpty()
                        || !sourceIds.containsAll(cited)) throw new IllegalStateException("Invalid candidate");
            }
        }
    }

    @Override
    public PageResult<Task> history(Long userId, int page, int size) {
        return historyPage(userId, page, size, null);
    }

    @Override
    public PageResult<Task> historyPage(Long userId, int page, int size, String taskType) {
        if(conversations!=null) conversations.getObject().cleanupOwner(userId);
        Page<Task> p = Page.of(Math.max(page, 1), Math.min(Math.max(size, 1), 100));
        Page<Task> result = baseMapper.selectPage(p, new LambdaQueryWrapper<Task>()
            .eq(Task::getUserId, userId).eq(taskType != null, Task::getTaskType, taskType)
            .isNull(Task::getDeletedAt)
            .orderByDesc(Task::getCreatedAt).orderByDesc(Task::getId));
        return PageResult.of(result.getTotal(), p.getCurrent(), p.getSize(), result.getRecords());
    }

    @Override
    public Task detail(Long userId, String taskId) {
        if(conversations!=null) conversations.getObject().cleanupOwner(userId);
        Task task = getById(taskId);
        if (task == null || !task.getUserId().equals(userId) || task.getDeletedAt() != null)
            throw new ApiException(404, "任务不存在或无权访问");
        return task;
    }

    @Override
    public void hideRecommendation(Long userId, String taskId) {
        Task task = detail(userId, taskId);
        if (!"SCHOOL_RECOMMEND".equals(task.getTaskType())) throw new ApiException(404, "推荐记录不存在");
        if (!"SUCCESS".equals(task.getStatus()) && !"FAILED".equals(task.getStatus()))
            throw new ApiException(409, "任务尚未结束，不能删除");
        if (baseMapper.hideRecommendation(userId, taskId, java.time.LocalDateTime.now()) != 1)
            throw new ApiException(404, "推荐记录不存在或已删除");
    }

    @Override
    public void run(ApplicationArguments args) {
        // Deployment contract: exactly one Java instance owns these synchronous tasks.
        for (Task task : baseMapper.selectList(new LambdaQueryWrapper<Task>().eq(Task::getStatus, "RUNNING"))) {
            task.setStatus("FAILED"); task.setErrorMessage("服务重启导致任务中断，请重新提交"); store.finish(task);
        }
    }
}
