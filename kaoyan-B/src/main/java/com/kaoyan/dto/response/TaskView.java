package com.kaoyan.dto.response;

import com.kaoyan.entity.Task;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.List;

/** Public projection deliberately excludes private model input and account identifiers. */
public record TaskView(String id,String taskType,String status,Map<String,Object> resultPayload,
                       String releaseId,String errorMessage,LocalDateTime createdAt,LocalDateTime updatedAt,
                       TutorTurn tutoring) {
    public static TaskView of(Task task) {
        return of(task,null);
    }

    public static TaskView of(Task task,TutorTurn turn) {
        return new TaskView(task.getId(),task.getTaskType(),task.getStatus(),task.getResultPayload(),task.getReleaseId(),
            task.getErrorMessage(),task.getCreatedAt(),task.getUpdatedAt(),turn);
    }

    /** Own-task conversation projection; never exposes attempt, profile, privacy or model context. */
    public record TutorTurn(long recordId, String query, String parentTaskId, List<Map<String,String>> messages) {
    }
}
