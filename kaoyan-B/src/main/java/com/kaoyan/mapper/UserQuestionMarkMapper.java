package com.kaoyan.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.kaoyan.dto.response.MarkQuestionVO;
import com.kaoyan.entity.UserQuestionMark;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * 错题与收藏 Mapper
 */
@Mapper
public interface UserQuestionMarkMapper extends BaseMapper<UserQuestionMark> {

    @Select("""
        SELECT m.question_id AS questionId,
               m.wrong_count AS wrongCount,
               m.last_wrong_at AS lastWrongAt,
               m.updated_at AS updatedAt,
               m.is_favorite AS isFavorite
        FROM user_question_mark m
        WHERE m.user_id = #{userId}
          AND m.is_wrong = 1
        ORDER BY m.last_wrong_at DESC, m.question_id DESC
        """)
    Page<MarkQuestionVO> pageWrong(Page<MarkQuestionVO> page, @Param("userId") Long userId);

    @Select("""
        SELECT m.question_id AS questionId,
               m.wrong_count AS wrongCount,
               m.last_wrong_at AS lastWrongAt,
               m.updated_at AS updatedAt,
               m.is_favorite AS isFavorite
        FROM user_question_mark m
        WHERE m.user_id = #{userId}
          AND m.is_favorite = 1
        ORDER BY m.updated_at DESC, m.question_id DESC
        """)
    Page<MarkQuestionVO> pageFavorite(Page<MarkQuestionVO> page, @Param("userId") Long userId);
}
