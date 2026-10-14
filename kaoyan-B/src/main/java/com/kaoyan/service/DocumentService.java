package com.kaoyan.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.kaoyan.common.PageResult;
import com.kaoyan.entity.Document;

import java.util.List;

/**
 * 备考资料 Service
 */
public interface DocumentService extends IService<Document> {

    /**
     * 已发布资料列表
     *
     * @param subject 科目（可空）
     * @return 资料列表
     */
    List<Document> listPublished(String subject);

    /**
     * 创建资料
     *
     * @param creatorUserId 创建人 ID
     * @param doc           资料
     * @return 资料
     */
    Document create(Long creatorUserId, Document doc);

    /**
     * 更新资料
     *
     * @param docId 资料 ID
     * @param doc   资料
     */
    void update(Long docId, Document doc);

    /**
     * 删除资料
     *
     * @param docId 资料 ID
     */
    void delete(Long docId);

    /**
     * 审核资料
     *
     * @param docId          资料 ID
     * @param reviewerUserId 审核人 ID
     * @param status          审核后状态
     * @param comment         审核意见
     */
    void review(Long docId, Long reviewerUserId, String status, String comment);

    /**
     * 按状态分页查询
     *
     * @param status 状态
     * @param page   页码
     * @param size   每页条数
     * @return 分页结果
     */
    PageResult<Document> listByStatus(String status, int page, int size);
}
