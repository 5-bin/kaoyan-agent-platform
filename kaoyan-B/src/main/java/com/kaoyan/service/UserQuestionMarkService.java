package com.kaoyan.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.kaoyan.common.PageResult;
import com.kaoyan.dto.response.MarkQuestionVO;
import com.kaoyan.entity.UserQuestionMark;

import java.util.List;

/**
 * 错题与收藏 Service
 */
public interface UserQuestionMarkService extends IService<UserQuestionMark> {

    void markWrong(Long userId, Long questionId);

    void toggleFavorite(Long userId, Long questionId, boolean favorite);

    void removeWrong(Long userId, Long questionId);

    /** 旧全量接口，保留兼容 */
    List<UserQuestionMark> listWrong(Long userId);
    List<UserQuestionMark> listFavorite(Long userId);

    /** 分页：错题（带题目详情） */
    PageResult<MarkQuestionVO> pageWrong(Long userId, int page, int size);

    /** 分页：收藏（带题目详情） */
    PageResult<MarkQuestionVO> pageFavorite(Long userId, int page, int size);

    boolean isFavorite(Long userId, Long questionId);
}
