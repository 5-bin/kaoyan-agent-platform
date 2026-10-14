package com.kaoyan.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.kaoyan.entity.Question;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

/**
 * 题库 Mapper
 */
@Mapper
public interface QuestionMapper extends BaseMapper<Question> {

    /**
     * 按条件抽题用于刷题：active=1 且已审核
     *
     * @param subject       科目（可空）
     * @param difficulty    难度（可空）
     * @param knowledgePoint 知识点（可空）
     * @param limit         抽取数量
     * @return 题目列表
     */
    @Select("<script>" +
            "SELECT * FROM question WHERE active = 1 AND review_status = 'APPROVED'" +
            "<if test='subject != null and subject != \"\"'> AND subject = #{subject}</if>" +
            "<if test='difficulty != null and difficulty != \"\"'> AND difficulty = #{difficulty}</if>" +
            "<if test='knowledgePoint != null and knowledgePoint != \"\"'> AND knowledge_point LIKE CONCAT('%', #{knowledgePoint}, '%')</if>" +
            " ORDER BY stable_order LIMIT #{limit}" +
            "</script>")
    List<Question> selectForPractice(@Param("subject") String subject,
                                     @Param("difficulty") String difficulty,
                                     @Param("knowledgePoint") String knowledgePoint,
                                     @Param("limit") int limit);
}
