package com.kaoyan.service;
import com.kaoyan.entity.Task;
import java.util.List;
import java.util.Map;
public interface RecommendService {
    Task generate(Long userId, Map<String, Object> input);
    List<Task> listByUser(Long userId);
    void delete(String taskId, Long userId);
}
