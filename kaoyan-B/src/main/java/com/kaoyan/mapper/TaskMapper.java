package com.kaoyan.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.kaoyan.entity.Task;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;
import java.time.LocalDateTime;

/**
 * Agent 任务 Mapper
 */
@Mapper
public interface TaskMapper extends BaseMapper<Task> {
    // Includes hidden history and failures: deleting a recommendation never refunds usage.
    @Select("SELECT COUNT(*) FROM task WHERE user_id=#{owner} AND created_at >= #{since}")
    long countForUserSince(@Param("owner") Long owner, @Param("since") LocalDateTime since);

    @Update("UPDATE task SET deleted_at=#{now}, updated_at=#{now} WHERE id=#{id} AND user_id=#{owner} "
        + "AND task_type='SCHOOL_RECOMMEND' AND status IN ('SUCCESS','FAILED') AND deleted_at IS NULL")
    int hideRecommendation(@Param("owner") Long owner, @Param("id") String id, @Param("now") LocalDateTime now);

    @Update("UPDATE task SET status='FAILED', result_payload=NULL, error_message=#{message}, updated_at=#{now} WHERE status='RUNNING'")
    int failInterruptedTasks(@Param("message") String message, @Param("now") LocalDateTime now);
}
