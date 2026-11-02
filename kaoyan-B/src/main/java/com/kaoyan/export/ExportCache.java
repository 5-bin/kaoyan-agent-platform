package com.kaoyan.export;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.common.ApiException;
import org.springframework.dao.DataAccessException;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Component;
import java.time.Instant;
import java.util.List;
import static com.kaoyan.export.ExportContracts.*;

/** Bounded Redis-only cache; one Lua operation orders concurrent creates and evictions. */
@Component
public class ExportCache {
    private final StringRedisTemplate redis;
    private final ObjectMapper json;
    private static final DefaultRedisScript<Long> SAVE = new DefaultRedisScript<>("""
        local old = redis.call('GET', KEYS[1])
        local entries = {}
        if old then
          for _, item in ipairs(cjson.decode(old)) do
            if item.expiresEpoch > tonumber(ARGV[2]) then table.insert(entries, item) end
          end
        end
        -- Preserve the nested JSON as a string: Lua cjson changes empty arrays into objects.
        table.insert(entries, {expiresEpoch=tonumber(ARGV[4]), id=ARGV[3], payload=ARGV[1]})
        while #entries > 5 do table.remove(entries, 1) end
        redis.call('SET', KEYS[1], cjson.encode(entries), 'EX', 900)
        return #entries
        """, Long.class);

    public ExportCache(StringRedisTemplate redis, ObjectMapper json) { this.redis = redis; this.json = json; }

    public void save(long owner, Cached snapshot) {
        try {
            String encoded = json.writeValueAsString(snapshot);
            if (encoded.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 2 * 1024 * 1024)
                throw new ApiException(413, "导出内容过大，请缩小范围");
            redis.execute(SAVE, List.of(key(owner)), encoded, Long.toString(Instant.now().getEpochSecond()),
                    snapshot.preview().id(), Long.toString(snapshot.expiresEpoch()));
        } catch (DataAccessException e) { throw unavailable(); }
        catch (JsonProcessingException e) { throw new ApiException(500, "导出快照生成失败"); }
    }

    public Cached get(long owner, String id) {
        if (!id.matches("[a-f0-9-]{36}")) throw missing();
        try {
            String value = redis.opsForValue().get(key(owner));
            if (value == null) throw missing();
            List<Slot> entries = json.readValue(value, new TypeReference<>() {});
            Slot slot = entries.stream().filter(item -> item.id().equals(id)
                    && item.expiresEpoch() > Instant.now().getEpochSecond()).findFirst().orElseThrow(ExportCache::missing);
            return json.readValue(slot.payload(), Cached.class);
        } catch (DataAccessException e) { throw unavailable(); }
        catch (JsonProcessingException e) { throw new ApiException(503, "导出快照暂不可用，请重新预览"); }
    }
    private record Slot(long expiresEpoch, String id, String payload) {}
    private static String key(long owner) { return "kaoyan:exports:v1:" + owner; }
    private static ApiException unavailable() { return new ApiException(503, "导出缓存暂不可用，请稍后重试"); }
    public static ApiException missing() { return new ApiException(404, "导出预览已过期或来源不可用，请重新预览"); }
}
