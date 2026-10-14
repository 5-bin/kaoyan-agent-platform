package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.common.ApiException;
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
import org.springframework.transaction.annotation.Transactional;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Agent 任务 Service 实现：提交后同步调 FastAPI 并落结果。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TaskServiceImpl extends ServiceImpl<TaskMapper, Task> implements TaskService {

    private final AgentFeignClient agentClient;
    private final AgentProperties agentProps;
    private final UserMapper userMapper;
    private final PracticeRecordMapper practiceRecordMapper;

    @Override
    @Transactional
    public Task submit(Long userId, String taskType, Map<String, Object> input) {
        Task t = new Task();
        t.setUserId(userId);
        t.setTaskType(taskType);
        t.setStatus("RUNNING");
        t.setInputPayload(input == null ? new HashMap<>() : new HashMap<>(input));
        save(t);
        try {
            AgentRequest req = buildRequest(userId, taskType, t.getId(), input);
            AgentResponse resp = agentClient.chat(agentProps.getInternalKey(), req);
            if (resp != null && "SUCCESS".equals(resp.getStatus())) {
                t.setStatus("SUCCESS");
                t.setResultPayload(toMap(resp.getResult()));
            } else {
                t.setStatus("FAILED");
                t.setErrorMessage(resp == null ? "no response" : resp.getErrorMessage());
            }
        } catch (Exception e) {
            log.warn("agent call failed taskId={} err={}", t.getId(), e.getMessage());
            t.setStatus("FAILED");
            t.setErrorMessage(e.getMessage());
        }
        updateById(t);
        return t;
    }

    @Override
    public List<Task> history(Long userId, int page, int size) {
        Page<Task> p = Page.of(Math.max(page, 1), Math.min(Math.max(size, 1), 100));
        return lambdaQuery()
                .eq(Task::getUserId, userId)
                .orderByDesc(Task::getCreatedAt)
                .page(p)
                .getRecords();
    }

    @Override
    public Task detail(Long userId, String taskId) {
        Task t = getById(taskId);
        if (t == null) {
            throw new ApiException(404, 404, "任务不存在");
        }
        if (!t.getUserId().equals(userId)) {
            throw new ApiException(403, 403, "无权访问");
        }
        return t;
    }

    private AgentRequest buildRequest(Long userId, String taskType, String taskId, Map<String, Object> input) {
        User u = userMapper.selectById(userId);
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

    @SuppressWarnings("unchecked")
    private Map<String, Object> toMap(Object o) {
        if (o instanceof Map) return (Map<String, Object>) o;
        Map<String, Object> m = new HashMap<>();
        m.put("data", o);
        return m;
    }
}
