package com.kaoyan.service.impl;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.kaoyan.common.ApiException;
import com.kaoyan.common.PageResult;
import com.kaoyan.entity.Document;
import com.kaoyan.mapper.DocumentMapper;
import com.kaoyan.service.DocumentService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 备考资料 Service 实现
 */
@Service
public class DocumentServiceImpl extends ServiceImpl<DocumentMapper, Document> implements DocumentService {

    @Override
    public List<Document> listPublished(String subject) {
        return lambdaQuery()
                .eq(Document::getStatus, "PUBLISHED")
                .eq(subject != null && !subject.isBlank(), Document::getSubject, subject)
                .orderByDesc(Document::getCreatedAt)
                .list();
    }

    @Override
    @Transactional
    public Document create(Long creatorUserId, Document doc) {
        doc.setId(null);
        doc.setStatus("DRAFT");
        doc.setCreatorUserId(creatorUserId);
        save(doc);
        return doc;
    }

    @Override
    @Transactional
    public void update(Long docId, Document doc) {
        Document exist = getById(docId);
        if (exist == null) {
            throw new ApiException(404, 404, "资料不存在");
        }
        doc.setId(docId);
        updateById(doc);
    }

    @Override
    @Transactional
    public void delete(Long docId) {
        if (!removeById(docId)) {
            throw new ApiException(404, 404, "资料不存在");
        }
    }

    @Override
    @Transactional
    public void review(Long docId, Long reviewerUserId, String status, String comment) {
        Document doc = getById(docId);
        if (doc == null) {
            throw new ApiException(404, 404, "资料不存在");
        }
        doc.setStatus(status);
        doc.setReviewerUserId(reviewerUserId);
        doc.setReviewedAt(LocalDateTime.now());
        updateById(doc);
    }

    @Override
    public PageResult<Document> listByStatus(String status, int page, int size) {
        Page<Document> p = Page.of(Math.max(page, 1), Math.min(Math.max(size, 1), 100));
        Page<Document> result = lambdaQuery()
                .eq(status != null && !status.isBlank(), Document::getStatus, status)
                .orderByDesc(Document::getCreatedAt)
                .page(p);
        return PageResult.of(result.getTotal(), result.getCurrent(), result.getSize(), result.getRecords());
    }
}
