package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.kaoyan.common.ApiException;
import com.kaoyan.config.AgentProperties;
import com.kaoyan.entity.Task;
import com.kaoyan.mapper.TaskMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.LocalDateTime;

/** Single Java instance: short reservation/finalization transactions, never remote calls. */
@Service
@RequiredArgsConstructor
public class TaskStore {
    private final TaskMapper mapper;
    private final AgentProperties props;

    @Transactional
    public synchronized void begin(Task task) {
        LocalDateTime now = LocalDateTime.now();
        long daily = mapper.selectCount(new LambdaQueryWrapper<Task>().eq(Task::getUserId, task.getUserId())
                .ge(Task::getCreatedAt, now.toLocalDate().atStartOfDay()));
        long minute = mapper.selectCount(new LambdaQueryWrapper<Task>().eq(Task::getUserId, task.getUserId())
                .ge(Task::getCreatedAt, now.minusMinutes(1)));
        if (daily >= props.getDailyTaskLimit() || minute >= props.getMinuteTaskLimit())
            throw new ApiException(429, "任务次数达到上限，请稍后再试");
        task.setCreatedAt(now);
        task.setUpdatedAt(now);
        mapper.insert(task);
    }

    @Transactional
    public void finish(Task task) {
        task.setUpdatedAt(LocalDateTime.now());
        if (mapper.updateById(task) != 1) throw new IllegalStateException("任务结果未保存");
    }
}
