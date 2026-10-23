package com.kaoyan.service;

import com.kaoyan.common.ApiException;
import com.kaoyan.config.AgentProperties;
import com.kaoyan.security.JwtService;
import lombok.RequiredArgsConstructor;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import java.net.URI;
import java.net.http.*;
import java.time.*;
import java.util.*;

/** Consent is account-owned. Neither browser fields nor model output grant access. */
@Service
@RequiredArgsConstructor
public class AssistantPrivacyService {
    public static final Set<String> SCOPES=Set.of("wrong","favorite","stats","profile","document");
    private final ChatRepository db;
    private final AgentProperties properties;
    private final JwtService jwt;
    private final TransactionTemplate transactions;
    private final ApplicationEventPublisher events;
    private final HttpClient http=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
    public record Changed(Long owner) {}
    public record Save(boolean modelAllowed,List<String> scopes,String provider) {}

    public String provider() {
        try {
            var response=http.send(HttpRequest.newBuilder(URI.create(properties.getBaseUrl()+"/health"))
                .timeout(Duration.ofSeconds(3)).GET().build(),HttpResponse.BodyHandlers.ofString());
            if(response.statusCode()!=200 || response.body().length()>4000) return "unavailable";
            var health=db.object(response.body());
            String value=Objects.toString(health.get("provider"),"");
            URI uri=URI.create(value);
            if(!"https".equals(uri.getScheme()) || uri.getHost()==null || uri.getUserInfo()!=null || uri.getQuery()!=null || uri.getFragment()!=null || value.length()>500)
                return "unavailable";
            return value;
        } catch(Exception ignored) { return "unavailable"; }
    }

    public Map<String,Object> settings(Long owner) { return settings(owner,provider()); }
    public Map<String,Object> settings(Long owner,String currentProvider) {
        var rows=db.rows("SELECT model_allowed,scopes_json,provider,version FROM assistant_privacy WHERE user_id=?",owner);
        var value=rows.isEmpty()?Map.<String,Object>of():rows.get(0);
        boolean enabled=Boolean.TRUE.equals(value.get("modelAllowed")) && !"unavailable".equals(currentProvider)
            && currentProvider.equals(value.get("provider"));
        var stored=db.object(value.get("scopes"));
        List<String> scopes=enabled?SCOPES.stream().filter(key -> Boolean.TRUE.equals(stored.get(key))).sorted().toList():List.of();
        Map<String,Object> out=new LinkedHashMap<>();
        out.put("modelAllowed",enabled); out.put("scopes",scopes); out.put("provider",currentProvider);
        out.put("version",value.getOrDefault("version",0)); out.put("retentionDays",30);
        return out;
    }

    public Map<String,Object> save(Long owner,Save input) {
        if(input==null || input.scopes()==null || input.scopes().size()>5 || !SCOPES.containsAll(input.scopes()))
            throw new ApiException(400,"隐私授权类别不合法");
        String provider=provider();
        if(input.modelAllowed() && ("unavailable".equals(provider) || !provider.equals(input.provider())))
            throw new ApiException(409,"模型接收端点已变化或不可用，请重新查看后授权");
        Map<String,Object> scopes=new TreeMap<>();
        if(input.modelAllowed()) input.scopes().forEach(key -> scopes.put(key,true));
        transactions.executeWithoutResult(tx -> {
            // Same account lock as task reservation; serializes first-time consent creation.
            db.one("SELECT id FROM `user` WHERE id=? FOR UPDATE",owner);
            var rows=db.rows("SELECT version FROM assistant_privacy WHERE user_id=?",owner);
            if(rows.isEmpty()) db.jdbc().update("INSERT INTO assistant_privacy(user_id,model_allowed,scopes_json,provider,version,consented_at) VALUES(?,?,?,?,1,CURRENT_TIMESTAMP)",
                owner,input.modelAllowed(),db.encode(scopes),provider);
            else db.jdbc().update("UPDATE assistant_privacy SET model_allowed=?,scopes_json=?,provider=?,version=version+1,consented_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                input.modelAllowed(),db.encode(scopes),provider,owner);
        });
        events.publishEvent(new Changed(owner));
        return settings(owner,provider);
    }

    public Map<String,Object> wire(Map<String,Object> settings) {
        return Map.of("modelAllowed",settings.get("modelAllowed"),"scopes",settings.get("scopes"),"version",settings.get("version"),"provider",settings.get("provider"));
    }

    public void check(Long owner,Map<String,Object> grant,int version) {
        var user=db.one("SELECT status FROM `user` WHERE id=? FOR UPDATE",owner);
        if(!(user.get("status") instanceof Number n) || n.intValue()!=1) throw new ApiException(401,"登录已失效");
        if(grant==null || !(grant.get("jti") instanceof String jti) || !(grant.get("expiresAt") instanceof Number expiry)
            || expiry.longValue()<=Instant.now().toEpochMilli() || jwt.isRevoked(jti)) throw new ApiException(401,"登录已失效");
        var rows=db.rows("SELECT version FROM assistant_privacy WHERE user_id=?",owner);
        int current=rows.isEmpty()?0:((Number)rows.get(0).get("version")).intValue();
        if(current!=version) throw new ApiException(409,"隐私授权已变化，请重新发起分析");
    }

    /** Conditional terminal write prevents a cleared synchronous request from restoring its payload. */
    public void finishTask(com.kaoyan.entity.Task task,Map<String,Object> grant,int version) {
        transactions.executeWithoutResult(tx -> {
            try { check(task.getUserId(),grant,version); }
            catch(ApiException error) { task.setStatus("FAILED");task.setResultPayload(null);task.setReleaseId(null);task.setErrorMessage("登录或隐私授权已变化，结果未保存"); }
            int changed=db.jdbc().update("UPDATE task SET status=?,result_payload=?,release_id=?,error_message=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=? AND status='RUNNING' AND deleted_at IS NULL",
                task.getStatus(),task.getResultPayload()==null?null:db.encode(task.getResultPayload()),task.getReleaseId(),task.getErrorMessage(),task.getId(),task.getUserId());
            if(changed==0) { task.setStatus("CANCELLED");task.setInputPayload(null);task.setResultPayload(null);task.setErrorMessage("记录已清除或请求已终止"); }
        });
    }

    /** Strip server-only routing and evidence identifiers before crossing the internal boundary. */
    public Object project(Object value) {
        if(value instanceof Map<?,?> map) {
            Map<String,Object> out=new LinkedHashMap<>();
            map.forEach((key,item) -> {
                String name=key.toString();
                if(!name.startsWith("_") && !Set.of("resource","questionId","sessionId","userId","ownerId","taskId","documentId","id").contains(name))
                    out.put(name,project(item));
            });
            return out;
        }
        if(value instanceof List<?> list) return list.stream().map(this::project).toList();
        return value;
    }
}
