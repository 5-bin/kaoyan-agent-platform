package com.kaoyan.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.kaoyan.entity.RecommendRecord;

import java.util.List;

/**
 * 择校推荐 Service
 */
public interface RecommendService extends IService<RecommendRecord> {

    /**
     * 为当前用户生成推荐记录
     *
     * @param userId 用户 ID
     * @return 推荐列表
     */
    List<RecommendRecord> generate(Long userId);

    /**
     * 列出某用户的推荐记录
     *
     * @param userId 用户 ID
     * @return 推荐列表
     */
    List<RecommendRecord> listByUser(Long userId);

    /**
     * 删除推荐记录（只能删自己的）
     *
     * @param recordId 记录 ID
     * @param userId   用户 ID
     */
    void delete(Long recordId, Long userId);
}
