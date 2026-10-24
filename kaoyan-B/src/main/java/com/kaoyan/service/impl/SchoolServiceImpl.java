package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.common.ApiException;
import com.kaoyan.dto.response.SchoolOptionsVO;
import com.kaoyan.entity.School;
import com.kaoyan.entity.SchoolDetail;
import com.kaoyan.mapper.SchoolMapper;
import com.kaoyan.service.SchoolDetailService;
import com.kaoyan.service.SchoolService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 院校 Service 实现
 */
@Service
@RequiredArgsConstructor
public class SchoolServiceImpl extends ServiceImpl<SchoolMapper, School> implements SchoolService {

    private final SchoolDetailService schoolDetailService;

    @Override
    public SchoolOptionsVO options() {
        return new SchoolOptionsVO(baseMapper.listProvinces(), baseMapper.listMajorNames());
    }

    @Override
    public List<School> search(String province, String level, String majorName) {
        return baseMapper.search(
                blankToNull(province),
                blankToNull(level),
                blankToNull(majorName));
    }

    private static String blankToNull(String s) {
        return (s == null || s.isBlank()) ? null : s;
    }

    @Override
    public Map<String, Object> detail(Long schoolId) {
        School school = getById(schoolId);
        if (school == null) {
            throw new ApiException(404, 404, "院校不存在");
        }
        List<SchoolDetail> details = schoolDetailService.listBySchool(schoolId);
        Map<String, Object> map = new HashMap<>();
        map.put("school", school);
        map.put("details", details);
        return map;
    }

    @Override
    public void create(School school) {
        school.setId(null);
        save(school);
    }

    @Override
    public void update(School school) {
        if (school.getId() == null || getById(school.getId()) == null) {
            throw new ApiException(404, 404, "院校不存在");
        }
        updateById(school);
    }

    @Override
    public void delete(Long schoolId) {
        if (!removeById(schoolId)) {
            throw new ApiException(404, 404, "院校不存在");
        }
        schoolDetailService.deleteBySchool(schoolId);
    }
}
