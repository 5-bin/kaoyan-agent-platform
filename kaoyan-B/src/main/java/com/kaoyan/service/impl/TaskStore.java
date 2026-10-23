package com.kaoyan.service.impl;

import com.kaoyan.common.ApiException;
import com.kaoyan.config.AgentProperties;
import com.kaoyan.entity.Task;
import com.kaoyan.mapper.TaskMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.LocalDateTime;
import java.time.Clock;
import java.time.ZoneOffset;

/** Single Java instance: short reservation/finalization transactions, never remote calls. */
@Service
@RequiredArgsConstructor
public class TaskStore {
    private final TaskMapper mapper;
    private final AgentProperties props;
    private Clock clock = Clock.systemDefaultZone();

    public boolean isQuotaExempt(Long owner) {
        String exempt = props.getQuotaExemptUsername();
        return exempt != null && !exempt.isBlank() && exempt.equals(mapper.quotaUsername(owner));
    }

    @Transactional
    public synchronized void begin(Task task) {
        mapper.lockQuotaAccount(task.getUserId());
        var instant = clock.instant();
        LocalDateTime now = LocalDateTime.ofInstant(instant, clock.getZone());
        var dayStart = instant.atOffset(ZoneOffset.UTC).toLocalDate().atStartOfDay().toInstant(ZoneOffset.UTC);
        long daily = mapper.countForUserSince(task.getUserId(), LocalDateTime.ofInstant(dayStart, clock.getZone()));
        long minute = mapper.countForUserSince(task.getUserId(), now.minusMinutes(1));
        if (!isQuotaExempt(task.getUserId()) && (daily >= props.getDailyTaskLimit() || minute >= props.getMinuteTaskLimit()))
            throw new ApiException(429, "任务次数达到上限；每日限额于UTC次日重置，分钟限额稍后恢复");
        task.setCreatedAt(now);
        task.setUpdatedAt(now);
        mapper.insert(task);
    }

    @Transactional
    public void finish(Task task) {
        task.setUpdatedAt(LocalDateTime.now(clock));
        if (mapper.updateById(task) != 1) throw new IllegalStateException("任务结果未保存");
    }
}
