package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.common.ApiException;
import com.kaoyan.entity.RecommendRecord;
import com.kaoyan.entity.School;
import com.kaoyan.mapper.RecommendRecordMapper;
import com.kaoyan.service.RecommendService;
import com.kaoyan.service.SchoolService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;

/**
 * 择校推荐 Service 实现
 */
@Service
@RequiredArgsConstructor
public class RecommendServiceImpl extends ServiceImpl<RecommendRecordMapper, RecommendRecord>
        implements RecommendService {

    private final SchoolService schoolService;

    @Override
    @Transactional
    public List<RecommendRecord> generate(Long userId) {
        // 占位实现：取前 5 所院校生成推荐；接入真实 Agent 后替换为模型输出
        List<School> schools = schoolService.list();
        if (schools.size() > 5) {
            schools = schools.subList(0, 5);
        }
        for (School s : schools) {
            RecommendRecord r = new RecommendRecord();
            r.setUserId(userId);
            r.setSchoolId(s.getId());
            r.setReason("占位推荐：" + s.getName());
            r.setScore(BigDecimal.ZERO);
            save(r);
        }
        return listByUser(userId);
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
