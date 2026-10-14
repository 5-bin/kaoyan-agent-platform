package com.kaoyan.service.impl;

import com.kaoyan.entity.Task;
import com.kaoyan.common.ApiException;
import com.kaoyan.service.RecommendService;
import com.kaoyan.service.TaskService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import java.util.List;
import java.util.Map;

/** One pipeline and one canonical history; never writes placeholder recommendation rows. */
@Service
@RequiredArgsConstructor
public class RecommendServiceImpl implements RecommendService {
    private final TaskService tasks;
    @Override public Task generate(Long userId, Map<String, Object> input) {
        return tasks.submit(userId, "SCHOOL_RECOMMEND", input == null
            ? Map.of("query", "请根据已保存档案比较2027年院校专业") : input);
    }
    @Override public List<Task> listByUser(Long userId) {
        return tasks.historyPage(userId, 1, 100, "SCHOOL_RECOMMEND").getList();
    }
    @Override public void delete(String taskId, Long userId) {
        Task task = tasks.detail(userId, taskId);
        if (!"SCHOOL_RECOMMEND".equals(task.getTaskType())) throw new ApiException(404, "推荐记录不存在");
        if ("RUNNING".equals(task.getStatus())) throw new ApiException(409, "任务处理中，不能删除");
        tasks.removeById(taskId);
    }
}
