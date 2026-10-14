package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.entity.SchoolDetail;
import com.kaoyan.mapper.SchoolDetailMapper;
import com.kaoyan.service.SchoolDetailService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 院校专业详情 Service 实现
 */
@Service
public class SchoolDetailServiceImpl extends ServiceImpl<SchoolDetailMapper, SchoolDetail>
        implements SchoolDetailService {

    @Override
    public List<SchoolDetail> listBySchool(Long schoolId) {
        return lambdaQuery()
                .eq(SchoolDetail::getSchoolId, schoolId)
                .orderByDesc(SchoolDetail::getYear)
                .list();
    }

    @Override
    public List<SchoolDetail> listBySchoolAndYear(Long schoolId, Integer year) {
        return lambdaQuery()
                .eq(SchoolDetail::getSchoolId, schoolId)
                .eq(year != null, SchoolDetail::getYear, year)
                .list();
    }

    @Override
    @Transactional
    public void batchSave(Long schoolId, List<SchoolDetail> details) {
        if (details == null || details.isEmpty()) {
            return;
        }
        details.forEach(d -> {
            d.setId(null);
            d.setSchoolId(schoolId);
        });
        saveBatch(details);
    }

    @Override
    @Transactional
    public void deleteBySchool(Long schoolId) {
        lambdaUpdate().eq(SchoolDetail::getSchoolId, schoolId).remove();
    }
}
