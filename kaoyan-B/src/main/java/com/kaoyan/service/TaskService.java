package com.kaoyan.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.kaoyan.entity.Task;
import com.kaoyan.common.PageResult;

import java.util.List;
import java.util.Map;

/**
 * Agent 任务 Service
 */
public interface TaskService extends IService<Task> {

    /**
     * 提交任务
     *
     * @param userId   用户 ID
     * @param taskType 任务类型
     * @param input    输入参数
     * @return 任务
     */
    Task submit(Long userId, String taskType, Map<String, Object> input);

    /**
     * 任务历史
     *
     * @param userId 用户 ID
     * @param page   页码
     * @param size   每页条数
     * @return 任务列表
     */
    List<Task> history(Long userId, int page, int size);
    PageResult<Task> historyPage(Long userId, int page, int size, String taskType);

    /**
     * 任务详情
     *
     * @param userId 用户 ID
     * @param taskId 任务 ID
     * @return 任务
     */
    Task detail(Long userId, String taskId);
}
