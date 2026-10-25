package com.kaoyan.dto.response;

import com.kaoyan.entity.Task;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.List;
import java.util.ArrayList;

/** Public projection deliberately excludes private model input and account identifiers. */
public record TaskView(String id,String taskType,String status,Map<String,Object> resultPayload,
                       String releaseId,String errorMessage,LocalDateTime createdAt,LocalDateTime updatedAt,
                       TutorTurn tutoring) {
    public static TaskView of(Task task) {
        return new TaskView(task.getId(),task.getTaskType(),task.getStatus(),task.getResultPayload(),task.getReleaseId(),
            task.getErrorMessage(),task.getCreatedAt(),task.getUpdatedAt(),TutorTurn.of(task));
    }

    /** Own-task conversation projection; never exposes attempt, profile, privacy or model context. */
    public record TutorTurn(long recordId, String query, String parentTaskId, List<Map<String,String>> messages) {
        static TutorTurn of(Task task) {
            var input = task.getInputPayload();
            if (!"WRONG_QUESTION_TUTOR".equals(task.getTaskType()) || input == null
                || !(input.get("recordId") instanceof Number id) || id.longValue() <= 0
                || !(input.get("query") instanceof String query) || query.length() > 2000) return null;
            List<Map<String,String>> messages = new ArrayList<>();
            if (input.get("messages") instanceof List<?> history) {
                for (Object item : history) {
                    if (item instanceof Map<?,?> message && message.get("role") instanceof String role
                        && (role.equals("user") || role.equals("assistant"))
                        && message.get("content") instanceof String content && content.length() <= 4000)
                        messages.add(Map.of("role",role,"content",content));
                }
            }
            return new TutorTurn(id.longValue(),query,input.get("parentTaskId") instanceof String parent ? parent : null,
                List.copyOf(messages.subList(Math.max(0,messages.size()-6),messages.size())));
        }
    }
}
