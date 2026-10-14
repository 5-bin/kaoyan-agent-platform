package com.kaoyan.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.kaoyan.entity.SchoolDetail;

import java.util.List;

/**
 * 院校专业详情 Service
 */
public interface SchoolDetailService extends IService<SchoolDetail> {

    /**
     * 列出某院校全部专业
     *
     * @param schoolId 院校 ID
     * @return 专业列表
     */
    List<SchoolDetail> listBySchool(Long schoolId);

    /**
     * 列出某院校某年专业
     *
     * @param schoolId 院校 ID
     * @param year     年份
     * @return 专业列表
     */
    List<SchoolDetail> listBySchoolAndYear(Long schoolId, Integer year);

    /**
     * 批量保存专业
     *
     * @param schoolId 院校 ID
     * @param details  专业列表
     */
    void batchSave(Long schoolId, List<SchoolDetail> details);

    /**
     * 删除某院校全部专业
     *
     * @param schoolId 院校 ID
     */
    void deleteBySchool(Long schoolId);
}
