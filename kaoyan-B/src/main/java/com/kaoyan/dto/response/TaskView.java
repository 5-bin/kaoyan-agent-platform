package com.kaoyan.dto.response;

import com.kaoyan.entity.Task;
import java.time.LocalDateTime;
import java.util.Map;

/** Public projection deliberately excludes private model input and account identifiers. */
public record TaskView(String id,String taskType,String status,Map<String,Object> resultPayload,
                       String releaseId,String errorMessage,LocalDateTime createdAt,LocalDateTime updatedAt) {
    public static TaskView of(Task task) {
        return new TaskView(task.getId(),task.getTaskType(),task.getStatus(),task.getResultPayload(),task.getReleaseId(),
            task.getErrorMessage(),task.getCreatedAt(),task.getUpdatedAt());
    }
}
