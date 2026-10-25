package com.kaoyan.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.kaoyan.dto.response.SchoolOptionsVO;
import com.kaoyan.entity.School;

import java.util.List;
import java.util.Map;

/**
 * 院校 Service
 */
public interface SchoolService extends IService<School> {

    /** 库内全部有效省份、专业名，不随当前筛选条件缩减。 */
    SchoolOptionsVO options();

    /**
     * 搜索院校
     *
     * @param province 省份（可空）
     * @param level    层次（可空）
     * @param majorName 专业名（可空，联表搜索）
     * @return 院校列表
     */
    List<School> search(String province, String level, String majorName);

    /**
     * 院校详情（含专业列表）
     *
     * @param schoolId 院校 ID
     * @return 详情
     */
    Map<String, Object> detail(Long schoolId);

    /**
     * 新建院校
     *
     * @param school 院校
     */
    void create(School school);

    /**
     * 更新院校
     *
     * @param school 院校
     */
    void update(School school);

    /**
     * 删除院校
     *
     * @param schoolId 院校 ID
     */
    void delete(Long schoolId);
}
