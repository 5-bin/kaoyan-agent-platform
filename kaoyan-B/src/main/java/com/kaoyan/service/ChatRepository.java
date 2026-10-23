package com.kaoyan.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.common.ApiException;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import java.util.*;

/** Small typed-boundary adapter for the additive chat tables. */
@Repository
@RequiredArgsConstructor
public class ChatRepository {
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;

    public JdbcTemplate jdbc() { return jdbc; }

    public String encode(Object value) {
        try { return json.writeValueAsString(value); }
        catch (Exception e) { throw new IllegalStateException("无法保存聊天记录"); }
    }

    public Map<String,Object> object(Object value) {
        if (value instanceof Map<?,?> map) {
            Map<String,Object> result = new LinkedHashMap<>();
            map.forEach((key, item) -> result.put(key.toString(), item));
            return result;
        }
        if (value == null) return new LinkedHashMap<>();
        try { return json.readValue(value.toString(), new TypeReference<>() {}); }
        catch (Exception e) { throw new IllegalStateException("聊天记录格式错误"); }
    }

    public List<Map<String,Object>> rows(String sql, Object... args) {
        return jdbc.query(sql, (rs, number) -> {
            Map<String,Object> result = new LinkedHashMap<>();
            var metadata = rs.getMetaData();
            for (int i = 1; i <= metadata.getColumnCount(); i++) {
                String raw = metadata.getColumnLabel(i).toLowerCase(Locale.ROOT);
                boolean encoded = raw.endsWith("_json");
                if (encoded) raw = raw.substring(0, raw.length() - 5);
                StringBuilder key = new StringBuilder();
                boolean upper = false;
                for (char c : raw.toCharArray()) {
                    if (c == '_') { upper = true; continue; }
                    key.append(upper ? Character.toUpperCase(c) : c); upper = false;
                }
                Object value = rs.getObject(i);
                if (encoded && value != null) value = object(rs.getString(i));
                if (value instanceof java.sql.Timestamp timestamp) value = timestamp.toLocalDateTime().toString();
                result.put(key.toString(), value);
            }
            return result;
        }, args);
    }

    public Map<String,Object> one(String sql, Object... args) {
        var result = rows(sql, args);
        if (result.isEmpty()) throw new ApiException(404, "记录不存在或无权访问");
        return result.get(0);
    }

    public Map<String,Object> page(String select, String count, int page, int size, Object... args) {
        if (page < 1 || size < 1 || size > 100) throw new ApiException(400, "分页参数不合法");
        Object[] paged = Arrays.copyOf(args, args.length + 2);
        paged[args.length] = size; paged[args.length + 1] = (page - 1) * size;
        return Map.of("list", rows(select + " LIMIT ? OFFSET ?", paged), "total", jdbc.queryForObject(count, Long.class, args),
            "pageNum", page, "pageSize", size);
    }
}
