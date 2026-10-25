package com.kaoyan.service;

import com.kaoyan.common.ApiException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;

@Service
@RequiredArgsConstructor
public class PersonalDocumentService {
    private final ChatRepository db;

    public record Save(String title, String content, Integer baseVersion) {}

    public Map<String,Object> list(Long owner, int page, int size) {
        return db.page("SELECT id,title,version,created_at,updated_at FROM personal_document WHERE user_id=? ORDER BY updated_at DESC,id",
            "SELECT COUNT(*) FROM personal_document WHERE user_id=?", page, size, owner);
    }
    public Map<String,Object> get(Long owner, String id) {
        return db.one("SELECT id,title,content,version,created_at,updated_at FROM personal_document WHERE user_id=? AND id=?", owner,id);
    }
    public Map<String,Object> versions(Long owner, String id, int page, int size) {
        get(owner,id);
        return db.page("SELECT document_id,version,title,content,source_task_id,created_at FROM personal_document_version WHERE user_id=? AND document_id=? ORDER BY version DESC",
            "SELECT COUNT(*) FROM personal_document_version WHERE user_id=? AND document_id=?",page,size,owner,id);
    }
    public Map<String,Object> version(Long owner,String id,int version) {
        get(owner,id);
        return db.one("SELECT document_id AS id,version,title,content,source_task_id,created_at FROM personal_document_version WHERE user_id=? AND document_id=? AND version=?",owner,id,version);
    }
    @Transactional
    public Map<String,Object> save(Long owner, String id, Save input, String taskId) {
        if (input == null || input.title() == null || input.title().isBlank() || input.title().length()>100
                || input.content()==null || input.content().length()>40000)
            throw new ApiException(400,"标题需为1—100字符，正文最多40000字符");
        if (taskId != null) {
            var previous = db.rows("SELECT document_id AS id,title,content,version FROM personal_document_version WHERE user_id=? AND source_task_id=?",owner,taskId);
            if (!previous.isEmpty()) return previous.get(0);
        }
        int version;
        if (id == null) {
            id=UUID.randomUUID().toString(); version=1;
            db.jdbc().update("INSERT INTO personal_document(id,user_id,title,content,version) VALUES(?,?,?,?,?)",id,owner,input.title().strip(),input.content(),version);
        } else {
            var current = db.one("SELECT version FROM personal_document WHERE id=? AND user_id=? FOR UPDATE",id,owner);
            version=((Number)current.get("version")).intValue()+1;
            if (input.baseVersion()==null || input.baseVersion()!=version-1)
                throw new ApiException(409,"笔记已有新版本，请重新读取并核对修改");
            db.jdbc().update("UPDATE personal_document SET title=?,content=?,version=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=? AND version=?",
                input.title().strip(),input.content(),version,id,owner,version-1);
        }
        db.jdbc().update("INSERT INTO personal_document_version(document_id,version,user_id,title,content,source_task_id) VALUES(?,?,?,?,?,?)",
            id,version,owner,input.title().strip(),input.content(),taskId);
        return get(owner,id);
    }
}
