package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.common.ApiException;
import com.kaoyan.common.PageResult;
import java.util.Set;
import java.util.Objects;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import com.kaoyan.config.AgentProperties;
import com.kaoyan.dto.agent.AgentRequest;
import com.kaoyan.dto.agent.AgentResponse;
import com.kaoyan.entity.PracticeRecord;
import com.kaoyan.entity.Task;
import com.kaoyan.entity.User;
import com.kaoyan.feign.AgentFeignClient;
import com.kaoyan.mapper.PracticeRecordMapper;
import com.kaoyan.mapper.TaskMapper;
import com.kaoyan.mapper.UserMapper;
import com.kaoyan.service.TaskService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Agent 任务 Service 实现：提交后同步调 FastAPI 并落结果。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TaskServiceImpl extends ServiceImpl<TaskMapper, Task> implements TaskService, ApplicationRunner {

    private final AgentFeignClient agentClient;
    private final AgentProperties agentProps;
    private final UserMapper userMapper;
    private final PracticeRecordMapper practiceRecordMapper;
    private Clock clock = Clock.systemDefaultZone();

    @Override
    public Task submit(Long userId, String taskType, Map<String, Object> input) {
        validateInput(taskType, input);
        // 授权和上下文校验先于任务创建；远程调用不持有数据库事务。
        AgentRequest req = buildRequest(userId, taskType, null, input);
        Task t = new Task();
        t.setUserId(userId);
        t.setTaskType(taskType);
        t.setStatus("RUNNING");
        t.setInputPayload(input == null ? new HashMap<>() : new HashMap<>(input));
        // 首版单Java实例：检查配额与落库在同一锁内，远程调用在锁外。
        synchronized (this) {
            Instant now = clock.instant();
            Instant dayStart = now.atOffset(ZoneOffset.UTC).toLocalDate().atStartOfDay().toInstant(ZoneOffset.UTC);
            if (baseMapper.countForUserSince(userId, LocalDateTime.ofInstant(dayStart, clock.getZone())) >= agentProps.getDailyTaskLimit())
                throw new ApiException(429, 429, "今日任务次数已达上限，UTC次日可再次提交");
            if (baseMapper.countForUserSince(userId, LocalDateTime.ofInstant(now.minusSeconds(60), clock.getZone())) >= agentProps.getMinuteTaskLimit())
                throw new ApiException(429, 429, "提交过于频繁，请稍后再试");
            t.setCreatedAt(LocalDateTime.now(clock));
            t.setUpdatedAt(t.getCreatedAt());
            save(t);
        }
        try {
            req.setTaskId(t.getId());
            AgentResponse resp = agentClient.chat(agentProps.getInternalKey(), req);
            if (resp == null || !Objects.equals(t.getId(), resp.getTaskId())
                    || !Set.of("SUCCESS", "FAILED").contains(Objects.toString(resp.getStatus(), ""))) {
                throw new IllegalStateException("Agent响应不符合契约");
            }
            if ("SUCCESS".equals(resp.getStatus())) {
                if (!(resp.getResult() instanceof Map<?, ?> result) || result.isEmpty()) {
                    throw new IllegalStateException("Agent结果缺失");
                }
                t.setStatus("SUCCESS");
                t.setResultPayload(toMap(resp.getResult()));
            } else {
                t.setStatus("FAILED");
                t.setErrorMessage("Agent未完成任务，请检查输入或稍后重试");
            }
        } catch (Exception e) {
            log.warn("agent call failed taskId={} type={}", t.getId(), e.getClass().getSimpleName());
            t.setStatus("FAILED");
            t.setErrorMessage("Agent暂时不可用或响应格式异常，请稍后查询任务记录");
        }
        t.setUpdatedAt(LocalDateTime.now(clock));
        updateById(t);
        return t;
    }

    @Override
    public PageResult<Task> history(Long userId, int page, int size) {
        Page<Task> p = Page.of(Math.max(page, 1), Math.min(Math.max(size, 1), 100));
        Page<Task> result = lambdaQuery()
                .eq(Task::getUserId, userId)
                .orderByDesc(Task::getCreatedAt)
                .page(p);
        return PageResult.of(result.getTotal(), result.getCurrent(), result.getSize(), result.getRecords());
    }

    @Override
    public Task detail(Long userId, String taskId) {
        Task t = getById(taskId);
        if (t == null || !Objects.equals(t.getUserId(), userId)) {
            throw new ApiException(404, 404, "任务不存在或无权访问");
        }
        return t;
    }

    @Override
    public void run(ApplicationArguments args) {
        int interrupted = baseMapper.failInterruptedTasks("服务重启导致任务中断，请检查记录后重新提交", LocalDateTime.now(clock));
        if (interrupted > 0) log.info("interruptedTasksMarkedFailed={}", interrupted);
    }

    private AgentRequest buildRequest(Long userId, String taskType, String taskId, Map<String, Object> input) {
        User u = "KNOWLEDGE_QA".equals(taskType) ? null : userMapper.selectById(userId);
        AgentRequest req = new AgentRequest();
        req.setTaskId(taskId);
        req.setUserId(userId);
        req.setTaskType(taskType);
        req.setProfile(buildProfile(u));
        if (input != null) {
            req.setUserInput((String) input.get("query"));
            req.setSessionId((String) input.get("sessionId"));
        }
        // 批次总结场景：从 practice_record 拉对错 id
        if ("PRACTICE_SUMMARY".equals(taskType) && input != null && input.get("sessionId") != null) {
            String sessionId = (String) input.get("sessionId");
            List<PracticeRecord> records = practiceRecordMapper.selectList(
                    new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<PracticeRecord>()
                            .eq(PracticeRecord::getUserId, userId)
                            .eq(PracticeRecord::getSessionId, sessionId));
            if (records.isEmpty()) throw new ApiException(404, 404, "批次不存在或无权访问");
            records = records.stream().filter(r -> "valid".equals(r.getGradingStatus())).toList();
            if (records.isEmpty() || records.stream().anyMatch(r -> r.getIsCorrect() == null))
                throw new ApiException(409, 409, "批次尚未完成或无有效作答，不能生成总结");
            List<Long> correct = records.stream().filter(r -> r.getIsCorrect() != null && r.getIsCorrect() == 1)
                    .map(PracticeRecord::getQuestionId).toList();
            List<Long> wrong = records.stream().filter(r -> r.getIsCorrect() != null && r.getIsCorrect() == 0)
                    .map(PracticeRecord::getQuestionId).toList();
            req.setCorrectQuestionIds(correct);
            req.setWrongQuestionIds(wrong);
        }
        return req;
    }

    private Map<String, Object> buildProfile(User u) {
        Map<String, Object> p = new HashMap<>();
        if (u != null) {
            p.put("targetSchool", u.getTargetSchool());
            p.put("targetMajor", u.getTargetMajor());
            p.put("examYear", u.getExamYear());
            p.put("background", u.getBackground());
        }
        return p;
    }

    static void validateInput(String type, Map<String, Object> input) {
        if (type == null || !Set.of("KNOWLEDGE_QA", "SCHOOL_RECOMMEND", "PRACTICE_SUMMARY", "CHAT").contains(type))
            throw new ApiException(400, 400, "不支持的任务类型");
        String field = "PRACTICE_SUMMARY".equals(type) ? "sessionId" : "query";
        int limit = "sessionId".equals(field) ? 64 : 8000;
        if (input == null || !input.keySet().equals(Set.of(field))
                || !(input.get(field) instanceof String text) || text.isBlank() || text.length() > limit)
            throw new ApiException(400, 400, "任务输入字段或长度不正确");
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> toMap(Object o) {
        return (Map<String, Object>) o; // 调用前已校验为非空对象。
    }
}
