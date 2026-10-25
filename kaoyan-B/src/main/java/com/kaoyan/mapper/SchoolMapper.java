package com.kaoyan.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.kaoyan.entity.School;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 院校 Mapper
 */
@Mapper
public interface SchoolMapper extends BaseMapper<School> {

    List<String> listProvinces();

    List<String> listMajorNames();

    /**
     * 多条件搜索院校：province / level / majorName 任意组合，都不传才查全部
     * （SQL 见 resources/mapper/SchoolMapper.xml）
     *
     * @param province  省份（精确）
     * @param level     层次（精确）
     * @param majorName 专业名（模糊，联表 school_detail）
     * @return 院校列表
     */
    List<School> search(@Param("province") String province,
                        @Param("level") String level,
                        @Param("majorName") String majorName);
}
