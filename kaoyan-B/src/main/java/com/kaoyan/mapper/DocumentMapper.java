package com.kaoyan.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.kaoyan.entity.Document;
import org.apache.ibatis.annotations.Mapper;

/**
 * 备考资料 Mapper
 */
@Mapper
public interface DocumentMapper extends BaseMapper<Document> {
}
