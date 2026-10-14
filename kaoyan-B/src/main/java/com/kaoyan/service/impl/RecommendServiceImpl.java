package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.common.ApiException;
import com.kaoyan.entity.RecommendRecord;
import com.kaoyan.mapper.RecommendRecordMapper;
import com.kaoyan.service.RecommendService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 择校推荐 Service 实现
 */
@Service
@RequiredArgsConstructor
public class RecommendServiceImpl extends ServiceImpl<RecommendRecordMapper, RecommendRecord>
        implements RecommendService {

    @Override
    public List<RecommendRecord> generate(Long userId) {
        // 正式候选和证据保存流程待接入，不能把任取前五所院校写成个人推荐。
        throw new ApiException(501, 501, "正式推荐记录生成尚未实现，请使用Agent任务查看实验性建议");
    }

    @Override
    public List<RecommendRecord> listByUser(Long userId) {
        return lambdaQuery()
                .eq(RecommendRecord::getUserId, userId)
                .orderByDesc(RecommendRecord::getCreatedAt)
                .list();
    }

    @Override
    @Transactional
    public void delete(Long recordId, Long userId) {
        RecommendRecord r = getById(recordId);
        if (r == null) {
            throw new ApiException(404, 404, "推荐记录不存在");
        }
        if (!r.getUserId().equals(userId)) {
            throw new ApiException(403, 403, "无权访问");
        }
        removeById(recordId);
    }
}
