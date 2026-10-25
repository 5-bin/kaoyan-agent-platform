package com.kaoyan.service.impl;

import com.kaoyan.common.ApiException;
import com.kaoyan.dto.agent.AgentRequest;
import com.kaoyan.entity.PracticeRecord;
import com.kaoyan.entity.Task;
import com.kaoyan.mapper.PracticeRecordMapper;
import com.kaoyan.mapper.TaskMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import java.util.*;

/** Builds a bounded conversation from owned, persisted data; no current-question fallback. */
@Component
@RequiredArgsConstructor
public class WrongQuestionTutorContext {
    private final PracticeRecordMapper records;
    private final TaskMapper tasks;

    public void populate(AgentRequest request, Long userId, Map<String, Object> input) {
        long recordId = positiveInteger(input.get("recordId"), 400);
        if (!(input.get("query") instanceof String query) || query.isBlank() || query.strip().length() > 2000)
            throw new ApiException(400, "辅导问题长度需为1—2000字符");
        PracticeRecord record = records.selectById(recordId);
        if (record == null || !userId.equals(record.getUserId())) throw new ApiException(404, "作答不存在或无权访问");
        if (!"valid".equals(record.getGradingStatus()) || !Integer.valueOf(0).equals(record.getIsCorrect())
                || record.getAnsweredAt() == null)
            throw new ApiException(409, "仅支持已提交且有效的错题作答");
        Map<String, Object> saved = record.getQuestionSnapshot();
        if (saved == null || record.getQuestionId() == null || positiveInteger(saved.get("id"), 409) != record.getQuestionId()) throw missing();
        positiveInteger(saved.get("version"), 409);
        Map<String, Object> attempt = new LinkedHashMap<>();
        attempt.put("recordId", recordId);
        for (String key : List.of("id", "version", "subject", "knowledgePoint", "content", "optionA", "optionB", "optionC", "optionD", "answer", "analysis")) {
            Object value = saved.get(key);
            if (!Set.of("id", "version", "knowledgePoint", "analysis").contains(key)) {
                int max = key.equals("subject") ? 50 : key.equals("answer") ? 1 : 10000;
                if (!(value instanceof String text) || text.isBlank() || text.length() > max) throw missing();
            } else if (Set.of("knowledgePoint", "analysis").contains(key) && value != null
                    && (!(value instanceof String text) || text.length() > (key.equals("analysis") ? 10000 : 255))) throw missing();
            attempt.put(key, value);
        }
        if (!(attempt.get("answer") instanceof String answer) || !answer.matches("[A-D]")
                || record.getUserAnswer() == null || !record.getUserAnswer().matches("[A-D]")
                || answer.equals(record.getUserAnswer())) throw missing();
        attempt.put("userAnswer", record.getUserAnswer());
        request.setAttempt(attempt);
        request.setUserInput(query.strip());
        List<Object> messages = new ArrayList<>();
        if (input.containsKey("parentTaskId")) {
            if (!(input.get("parentTaskId") instanceof String parentId) || !parentId.matches("[A-Za-z0-9_-]{1,64}"))
                throw new ApiException(400, "父任务编号不合法");
            Task parent = tasks.selectById(parentId);
            if (parent == null || !userId.equals(parent.getUserId()) || parent.getDeletedAt() != null)
                throw new ApiException(404, "父任务不存在或无权访问");
            Map<String, Object> previous = parent.getInputPayload();
            if (!"WRONG_QUESTION_TUTOR".equals(parent.getTaskType()) || !"SUCCESS".equals(parent.getStatus())
                    || previous == null || positiveInteger(previous.get("recordId"), 409) != recordId
                    || !sameAttempt(attempt, previous.get("attempt")))
                throw new ApiException(409, "父任务必须是同一次作答的成功辅导任务");
            // Previous context was generated here, not accepted from the browser.
            if (previous.get("messages") instanceof List<?> history) messages.addAll(history);
            messages.add(Map.of("role", "user", "content", previous.get("query"), "scopes", List.of("wrong")));
            messages.add(Map.of("role", "assistant", "content", parent.getResultPayload().get("answer"), "scopes", List.of("wrong")));
            if (messages.size() > 6) messages = new ArrayList<>(messages.subList(messages.size() - 6, messages.size()));
        }
        request.setMessages(messages);
    }

    private static long positiveInteger(Object value, int code) {
        if (!(value instanceof Byte || value instanceof Short || value instanceof Integer || value instanceof Long)
                || ((Number) value).longValue() <= 0) throw new ApiException(code, "缺少合法的作答题号或版本编号");
        return ((Number) value).longValue();
    }
    private static ApiException missing() { return new ApiException(409, "历史作答快照不完整或不一致，无法辅导；不会使用现行题目替代"); }
    private static boolean sameAttempt(Map<String, Object> current, Object previous) {
        if (!(previous instanceof Map<?, ?> saved) || !current.keySet().equals(saved.keySet())) return false;
        return current.entrySet().stream().allMatch(e -> Set.of("id", "version", "recordId").contains(e.getKey())
            ? Objects.toString(e.getValue()).equals(Objects.toString(saved.get(e.getKey())))
            : Objects.equals(e.getValue(), saved.get(e.getKey())));
    }
}
