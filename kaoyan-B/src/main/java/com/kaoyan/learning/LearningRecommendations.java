package com.kaoyan.learning;

import com.kaoyan.common.ApiException;
import com.kaoyan.config.AgentProperties;
import com.kaoyan.dto.agent.*;
import com.kaoyan.entity.Task;
import com.kaoyan.mapper.TaskMapper;
import com.kaoyan.service.*;
import com.kaoyan.service.impl.*;
import com.kaoyan.feign.AgentFeignClient;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.transaction.annotation.Transactional;
import java.net.URI;
import java.net.http.*;
import java.time.*;
import java.util.*;
import static com.kaoyan.learning.ManagedPracticeService.*;

@Service
@RequiredArgsConstructor
@ConditionalOnProperty(name="kaoyan.learning.enabled", havingValue="true")
public class LearningRecommendations {
    private final ChatRepository db;
    private final LearningProfiles profiles;
    private final TaskStore tasks;
    private final TaskMapper taskMapper;
    private final AgentFeignClient agent;
    private final AgentProperties properties;
    private final ReferenceSourcePolicy sources;
    private final TransactionTemplate tx;
    private final HttpClient http=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
    public Map<String,Object> settings(long owner) {
        var rows=db.rows("SELECT * FROM learning_recommendation_settings WHERE user_id=?",owner);
        if(rows.isEmpty())return Map.of("revision",0,"enabled",false,"preferences",Map.of(),"status","DISABLED");
        var s=rows.get(0);var out=new LinkedHashMap<String,Object>();
        out.put("revision",s.get("revision"));out.put("enabled",((Number)s.get("enabled")).intValue()==1);out.put("preferences",s.get("preferences"));
        out.put("status",s.get("pendingReason")==null?"CURRENT":((Number)s.get("attempts")).intValue()>=3?"FAILED":"PENDING");out.put("pendingReason",s.get("pendingReason"));out.put("notBefore",s.get("notBefore"));
        out.put("lastTaskId",s.get("lastTaskId"));out.put("profileRevision",s.get("lastProfileRevision"));out.put("updatedAt",s.get("lastCompletedAt"));return out;
    }
    @Transactional
    public Map<String,Object> save(long owner,LearningContracts.Settings req) {
        profiles.lock(owner);validatePreferences(req.preferences());
        var s=db.one("SELECT * FROM learning_recommendation_settings WHERE user_id=? FOR UPDATE",owner);
        if(((Number)s.get("revision")).intValue()!=req.revision())throw conflict("推荐设置已变化，请重新读取");
        var prefs=new LinkedHashMap<>(req.preferences());prefs.put("explainWithAi",false);
        db.jdbc().update("UPDATE learning_recommendation_settings SET revision=revision+1,enabled=?,preferences_json=?,pending_reason=?,not_before=?,run_token=NULL,run_until=NULL,pending_task_id=NULL,attempts=0 WHERE user_id=?",
            req.enabled()?1:0,db.encode(prefs),req.enabled()?"CONDITIONS_CHANGED":null,now(),owner);
        return settings(owner);
    }
    private void validatePreferences(Map<String,Object> p) {
        if(!Set.of("majorCodes","degreeType","regions","regionConstraint","studyMode","examSubjects","explainWithAi").containsAll(p.keySet()))throw new ApiException(400,"未知推荐条件");
        for(var e:Map.of("majorCodes",10,"regions",30,"examSubjects",4).entrySet())if(p.containsKey(e.getKey())) {
            if(!(p.get(e.getKey()) instanceof List<?> list)||list.size()>e.getValue())throw new ApiException(400,"推荐列表无效");
            for(var v:list)if(!(v instanceof String text)||text.isBlank()||text.length()>50||e.getKey().equals("majorCodes")&&!text.matches("[0-9]{6}")||e.getKey().equals("examSubjects")&&!text.matches("[0-9]{3}"))throw new ApiException(400,"推荐条件格式无效");
        }
        for(var e:Map.of("degreeType",Set.of("academic","professional"),"regionConstraint",Set.of("required","preferred"),"studyMode",Set.of("full_time","part_time")).entrySet())
            if(p.containsKey(e.getKey())&&!e.getValue().contains(p.get(e.getKey())))throw new ApiException(400,"推荐枚举无效");
        if(p.containsKey("explainWithAi")&&!(p.get("explainWithAi") instanceof Boolean))throw new ApiException(400,"解释开关无效");
    }
    public String release() {
        try {
            var response=http.send(HttpRequest.newBuilder(URI.create(properties.getBaseUrl()+"/health")).timeout(Duration.ofSeconds(3)).GET().build(),HttpResponse.BodyHandlers.ofString());
            if(response.statusCode()!=200||response.body().length()>4000)return null;
            Object value=db.object(response.body()).get("releaseId");return value instanceof String s&&s.matches("rag-v1-[a-f0-9]{16}")?s:null;
        } catch(Exception e) {return null;}
    }
    /** One service-level rules call: no browser session grant and no external-model permission. */
    public void run(long owner,String release) {
        if(release==null)return;
        var claim=tx.execute(status -> {
            profiles.lock(owner);var s=db.one("SELECT * FROM learning_recommendation_settings WHERE user_id=? FOR UPDATE",owner);
            var user=db.one("SELECT status,target_school,target_major,exam_year FROM `user` WHERE id=?",owner);
            if(((Number)user.get("status")).intValue()!=1||((Number)s.get("enabled")).intValue()!=1)return null;
            String profileHash=hash(db.encode(user));
            boolean changed=!Objects.equals(release,s.get("lastReleaseId"))||!Objects.equals(profileHash,s.get("lastProfileHash"));
            if(changed&&!"CONDITIONS_CHANGED".equals(s.get("pendingReason"))&&!"SOURCE_CHANGED".equals(s.get("pendingReason"))) {
                db.jdbc().update("UPDATE learning_recommendation_settings SET pending_reason='SOURCE_CHANGED',not_before=?,revision=revision+1,attempts=0,pending_task_id=NULL WHERE user_id=?",now(),owner);
                s=db.one("SELECT * FROM learning_recommendation_settings WHERE user_id=?",owner);
            }
            if(s.get("pendingReason")==null||((Number)s.get("attempts")).intValue()>=3)return null;
            if(s.get("notBefore")!=null&&LocalDateTime.parse(s.get("notBefore").toString()).isAfter(now()))return null;
            if(s.get("runUntil")!=null&&LocalDateTime.parse(s.get("runUntil").toString()).isAfter(now()))return null;
            String token=UUID.randomUUID().toString();var snapshot=profiles.snapshot(owner);
            String pendingId=s.get("pendingTaskId") instanceof String existing?existing:null;
            Task pending=pendingId==null?null:taskMapper.selectById(pendingId);
            if(pending!=null&&!release.equals(pending.getInputPayload()==null?null:pending.getInputPayload().get("targetReleaseId")))pendingId=null;
            String id=pendingId!=null?pendingId:UUID.nameUUIDFromBytes((owner+":"+s.get("revision")+":"+snapshot.get("profileRevision")+":"+release).getBytes(java.nio.charset.StandardCharsets.UTF_8)).toString();
            var task=taskMapper.selectById(id);
            if(task==null) {
                task=new Task();task.setId(id);task.setUserId(owner);task.setTaskType("SCHOOL_RECOMMEND");task.setStatus("RUNNING");
                task.setInputPayload(Map.of("learningSnapshot",snapshot,"targetReleaseId",release,"settingsRevision",s.get("revision"),"triggerReason",s.get("pendingReason"),"preferences",s.get("preferences")));
                tasks.begin(task);
            }
            db.jdbc().update("UPDATE learning_recommendation_settings SET run_token=?,run_until=?,pending_task_id=? WHERE user_id=?",token,now().plusMinutes(2),id,owner);
            var out=new LinkedHashMap<String,Object>();out.put("settings",s);out.put("user",user);out.put("hash",profileHash);out.put("token",token);out.put("task",task);return out;
        });
        if(claim==null)return;
        @SuppressWarnings("unchecked") var settings=(Map<String,Object>)claim.get("settings");
        @SuppressWarnings("unchecked") var user=(Map<String,Object>)claim.get("user");
        Task task=(Task)claim.get("task");boolean success="SUCCESS".equals(task.getStatus());
        try {
            if(!success) {
                var request=new AgentRequest();request.setTaskId(task.getId());request.setUserId(owner);request.setTaskType("SCHOOL_RECOMMEND");
                request.setUserInput("根据已保存条件与当前学情更新院校候选");request.setQuotaExempt(tasks.isQuotaExempt(owner));
                var profile=new LinkedHashMap<String,Object>();for(String k:List.of("targetSchool","targetMajor","examYear"))profile.put(k,user.get(k));request.setProfile(profile);
                request.setPreferences(db.object(settings.get("preferences")));request.setPrivacy(Map.of("modelAllowed",false,"scopes",List.of(),"version",0));
                request.setLearningSnapshot(db.object(task.getInputPayload().get("learningSnapshot")));
                var response=agent.chat(properties.getInternalKey(),request);TaskServiceImpl.validateResponse(task,response);sources.validateResponse(response);
                if(!release.equals(response.getReleaseId()))throw new IllegalStateException("release_changed");
                if(!"SUCCESS".equals(response.getStatus()))throw new IllegalStateException("rules_failed");
                var result=new LinkedHashMap<String,Object>(db.object(response.getResult()));result.put("references",response.getReferences());
                enrich(owner,result,request.getLearningSnapshot(),settings.get("pendingReason").toString());
                task.setReleaseId(response.getReleaseId());task.setResultPayload(result);task.setStatus("SUCCESS");task.setErrorMessage(null);success=true;
            }
        } catch(Exception e) {task.setStatus("FAILED");task.setErrorMessage("自动推荐暂时不可用，可稍后重试");}
        boolean completed=success;
        tx.executeWithoutResult(status -> {
            profiles.lock(owner);tasks.finish(task);
            if(completed) {
                var saved=db.object(task.getInputPayload().get("learningSnapshot"));
                var currentUser=db.one("SELECT status,target_school,target_major,exam_year FROM `user` WHERE id=?",owner);
                if(!claim.get("hash").equals(hash(db.encode(currentUser)))) {
                    db.jdbc().update("UPDATE learning_recommendation_settings SET pending_reason='CONDITIONS_CHANGED',not_before=?,revision=revision+1,attempts=0,run_token=NULL,run_until=NULL,pending_task_id=NULL WHERE user_id=? AND run_token=?",now(),owner,claim.get("token"));return;
                }
                // CAS against settings AND profile: an old result remains history, never the current pointer.
                if(profiles.profile(owner).revision()!=((Number)saved.get("profileRevision")).intValue()) {
                    db.jdbc().update("UPDATE learning_recommendation_settings SET run_token=NULL,run_until=NULL,pending_task_id=NULL,not_before=? WHERE user_id=? AND run_token=?",now(),owner,claim.get("token"));return;
                }
                db.jdbc().update("UPDATE learning_recommendation_settings SET last_task_id=?,last_profile_revision=?,last_score=?,last_sufficient=?,last_completed_at=?,last_release_id=?,last_profile_hash=?,pending_reason=NULL,not_before=NULL,run_token=NULL,run_until=NULL,pending_task_id=NULL,attempts=0 WHERE user_id=? AND run_token=? AND revision=?",
                    task.getId(),saved.get("profileRevision"),saved.get("referenceScore"),Boolean.TRUE.equals(saved.get("sufficient"))?1:0,now(),release,claim.get("hash"),owner,claim.get("token"),settings.get("revision"));
            } else db.jdbc().update("UPDATE learning_recommendation_settings SET attempts=attempts+1,run_token=NULL,run_until=NULL,not_before=? WHERE user_id=? AND run_token=?",now().plusSeconds(30),owner,claim.get("token"));
        });
    }
    public void enrich(long owner,Map<String,Object> result,Map<String,Object> snapshot,String reason) {
        result.put("resultSchemaVersion",2);result.put("learningSnapshot",snapshot);result.put("triggerReason",reason);
        if(!(result.get("candidates") instanceof List<?> list))return;
        var comparisons=new ArrayList<Map<String,Object>>();
        for(var item:list) {
            if(!(item instanceof Map<?,?> c))continue;
            var comparison=new LinkedHashMap<String,Object>();comparison.put("programId",c.get("programId"));comparison.put("status","NO_COMPARABLE_DATA");
            var metrics=db.rows("SELECT * FROM school_historical_metric WHERE program_id=? AND school=? AND college=? AND major_code=? AND metric_year<? AND metric_type='SUBJECT_CUTOFF' AND exam_subject='408' AND max_score=150 ORDER BY metric_year DESC,id ASC LIMIT 1",
                c.get("programId"),c.get("school"),c.get("college"),c.get("majorCode"),c.get("year"));
            if(c.get("examSubjects") instanceof List<?> subjects&&subjects.contains("408")&&!metrics.isEmpty()) {
                var m=metrics.get(0);comparison.put("year",m.get("metricYear"));comparison.put("score",m.get("score"));comparison.put("source",m.get("source"));
                if(snapshot.get("referenceScore") instanceof Number score) {comparison.put("status","EXPERIMENTAL_COMPARISON");comparison.put("gap",Math.round((score.doubleValue()-((Number)m.get("score")).doubleValue())*10)/10.0);}
                else comparison.put("status","INSUFFICIENT_LEARNING_DATA");
            }
            comparison.put("notice","历史408单科线仅供参考；学情估分未经整卷校准，不据此删除候选。");comparisons.add(comparison);
        }
        result.put("historicalComparisons",comparisons);
    }
    @Transactional
    public String addMetric(LearningContracts.Metric m,long reviewer) {
        if(!Double.isFinite(m.score())||m.score()>m.maxScore())throw new ApiException(400,"分数或满分无效");
        if("SUBJECT_CUTOFF".equals(m.metricType())&&m.examSubject()==null)throw new ApiException(400,"单科指标必须指定科目");
        if(!m.source().keySet().equals(Set.of("title","url","locator","version","retrievedAt","permissionNote")))throw new ApiException(400,"来源字段不完整");
        for(var v:m.source().values())if(!(v instanceof String text)||text.isBlank()||text.length()>2000)throw new ApiException(400,"来源信息无效");
        try {
            var retrieved=LocalDate.parse(m.source().get("retrievedAt").toString());
            if(retrieved.isAfter(now().toLocalDate())||m.year()>now().getYear())throw new IllegalArgumentException();
        } catch(Exception ignored) {throw new ApiException(400,"历史指标年份或来源获取日期无效");}
        sources.validateUrl(m.source().get("url").toString());
        String id=UUID.randomUUID().toString();db.jdbc().update("INSERT INTO school_historical_metric(id,program_id,school,college,major_code,metric_year,metric_type,exam_subject,max_score,score,source_json,reviewer_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            id,m.programId(),m.school(),m.college(),m.majorCode(),m.year(),m.metricType(),m.examSubject(),m.maxScore(),m.score(),db.encode(m.source()),reviewer,now());
        db.jdbc().update("UPDATE learning_recommendation_settings SET pending_reason='SOURCE_CHANGED',not_before=?,revision=revision+1,attempts=0,pending_task_id=NULL WHERE enabled=1",now());return id;
    }
}
