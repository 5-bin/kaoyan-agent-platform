package com.kaoyan.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.kaoyan.entity.Task;
import org.apache.ibatis.annotations.Mapper;

/**
 * Agent 任务 Mapper
 */
@Mapper
public interface TaskMapper extends BaseMapper<Task> {
}
