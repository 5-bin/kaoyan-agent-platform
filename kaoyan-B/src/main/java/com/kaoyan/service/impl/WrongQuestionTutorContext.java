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

    private java.time.Clock clock=java.time.Clock.systemDefaultZone();

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
        Object raw=input.get("parentTaskId");
        if(raw!=null && (!(raw instanceof String id)||!id.matches("[A-Za-z0-9_-]{1,64}")))
            throw new ApiException(400,"父任务编号不合法");
        request.setMessages(history(userId,recordId,attempt,(String)raw,true));
    }

    /** Reconstruct at most three original turns. Embedded legacy messages are ignored. */
    private List<Object> history(Long owner,long recordId,Map<String,Object> attempt,String parentId,boolean strictFirst) {
        List<List<Object>> turns=new ArrayList<>();Set<String> visited=new HashSet<>();
        var cutoff=java.time.LocalDateTime.now(clock).minusDays(30);
        while(parentId!=null && turns.size()<3 && visited.add(parentId)) {
            Task parent=tasks.selectById(parentId);
            boolean visible=parent!=null && owner.equals(parent.getUserId()) && parent.getDeletedAt()==null;
            var input=visible?parent.getInputPayload():null;
            boolean eligible=visible && parent.getCreatedAt()!=null && !parent.getCreatedAt().isBefore(cutoff)
                && "WRONG_QUESTION_TUTOR".equals(parent.getTaskType()) && "SUCCESS".equals(parent.getStatus())
                && input!=null && input.get("recordId") instanceof Number n && n.longValue()==recordId
                && sameAttempt(attempt,input.get("attempt")) && input.get("query") instanceof String query && !query.isBlank() && query.length()<=2000
                && parent.getResultPayload()!=null && parent.getResultPayload().get("answer") instanceof String answer && !answer.isBlank() && answer.length()<=4000;
            if(!eligible) {
                if(strictFirst && turns.isEmpty())throw new ApiException(visible?409:404,visible?"父任务已过期或不是同一次作答的成功辅导":"父任务不存在或无权访问");
                break;
            }
            turns.add(List.of(Map.of("role","user","content",input.get("query"),"scopes",List.of("wrong")),
                Map.of("role","assistant","content",parent.getResultPayload().get("answer"),"scopes",List.of("wrong"))));
            parentId=input.get("parentTaskId") instanceof String next?next:null;
        }
        Collections.reverse(turns);List<Object> messages=new ArrayList<>();turns.forEach(messages::addAll);return messages;
    }

    /** Public history uses exactly the same source filtering as model history. */
    public com.kaoyan.dto.response.TaskView.TutorTurn turn(Task task) {
        var input=task.getInputPayload();
        if(!"WRONG_QUESTION_TUTOR".equals(task.getTaskType()) || task.getDeletedAt()!=null || input==null
            || !(input.get("recordId") instanceof Number id) || !(input.get("query") instanceof String query))return null;
        String parent=input.get("parentTaskId") instanceof String value?value:null;
        Map<String,Object> attempt=input.get("attempt") instanceof Map<?,?> value?(Map<String,Object>)value:Map.of();
        var messages=history(task.getUserId(),id.longValue(),attempt,parent,false).stream().map(value -> {
            var row=(Map<?,?>)value;return Map.of("role",row.get("role").toString(),"content",row.get("content").toString());
        }).toList();
        return new com.kaoyan.dto.response.TaskView.TutorTurn(id.longValue(),query,parent,messages);
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
