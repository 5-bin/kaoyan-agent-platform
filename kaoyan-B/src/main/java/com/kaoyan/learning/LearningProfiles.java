package com.kaoyan.learning;

import com.kaoyan.common.ApiException;
import com.kaoyan.service.ChatRepository;
import com.kaoyan.entity.PracticeRecord;
import com.kaoyan.mapper.PracticeRecordMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.learning.LearningContracts.*;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;
import static com.kaoyan.learning.ManagedPracticeService.*;

@Service
@RequiredArgsConstructor
@ConditionalOnProperty(name="kaoyan.learning.enabled", havingValue="true")
public class LearningProfiles {
    private final ChatRepository db;
    private final ObjectMapper json;
    private final PracticeRecordMapper records;
    private final LearningProfileEngine engine=new LearningProfileEngine();
    @Transactional
    public void ensure(long owner) {
        db.one("SELECT id FROM `user` WHERE id=? FOR UPDATE",owner);
        if(db.rows("SELECT user_id FROM learning_profile WHERE user_id=?",owner).isEmpty()) {
            var initial=engine.calculate(List.of(),List.of(),"unpublished",0,now());
            db.jdbc().update("INSERT INTO learning_profile(user_id,revision,data_json,updated_at) VALUES(?,0,?,?)",owner,db.encode(initial),now());
        }
        if(db.rows("SELECT user_id FROM learning_recommendation_settings WHERE user_id=?",owner).isEmpty())
            db.jdbc().update("INSERT INTO learning_recommendation_settings(user_id,revision,enabled,preferences_json) VALUES(?,0,0,'{}')",owner);
    }
    @Transactional
    public void lock(long owner) {ensure(owner);db.one("SELECT user_id FROM learning_profile WHERE user_id=? FOR UPDATE",owner);}
    public Profile profile(long owner) {
        var result=db.rows("SELECT data_json FROM learning_profile WHERE user_id=?",owner);
        return result.isEmpty()?engine.calculate(List.of(),List.of(),"unpublished",0,now()):json.convertValue(result.get(0).get("data"),Profile.class);
    }
    @Transactional
    public void event(long owner,String key) {
        if(!db.rows("SELECT id FROM learning_event WHERE event_key=?",owner+":"+key).isEmpty())return;
        db.jdbc().update("INSERT INTO learning_event(id,user_id,event_key,state,next_at,created_at) VALUES(?,?,?,'PENDING',?,?)",UUID.randomUUID().toString(),owner,owner+":"+key,now(),now());
    }
    public List<Cell> cells() {
        var rows=db.rows("SELECT config_json FROM learning_blueprint ORDER BY created_at DESC,id ASC LIMIT 1");
        if(rows.isEmpty())return List.of();
        var config=db.object(rows.get(0).get("config"));
        return ((List<?>)config.get("cells")).stream().map(v -> json.convertValue(v,Cell.class)).toList();
    }
    public String blueprintVersion() {
        var rows=db.rows("SELECT id,version FROM learning_blueprint ORDER BY created_at DESC,id ASC LIMIT 1");
        return rows.isEmpty()?"unpublished":rows.get(0).get("id")+":"+rows.get(0).get("version");
    }
    @Transactional
    public void publish(Blueprint blueprint,long reviewer) {
        double sum=blueprint.cells().stream().mapToDouble(Cell::weight).sum();
        if(!Double.isFinite(sum)||Math.abs(sum-1)>0.000001||blueprint.cells().stream().mapToInt(Cell::count).sum()>50||blueprint.cells().stream().map(Cell::subject).distinct().count()!=4
            ||!blueprint.cells().stream().map(Cell::subject).collect(java.util.stream.Collectors.toSet()).equals(Set.of("数据结构","计算机组成原理","操作系统","计算机网络")))
            throw new ApiException(400,"蓝图必须覆盖四科、权重和为1，题数最多50");
        var keys=new HashSet<String>();for(var c:blueprint.cells())
            if(!c.knowledgePointId().equals(LearningProfileEngine.pointId(c.subject(),c.knowledgePoint()))||!keys.add(c.knowledgePointId()+":"+c.difficulty()))
                throw new ApiException(400,"知识点编号须等于subject:knowledgePoint的SHA256前24位且分组不得重复");
        if(!db.rows("SELECT id FROM learning_blueprint WHERE id=?",blueprint.id()).isEmpty())throw conflict("蓝图不可覆盖，请使用新发布编号");
        db.jdbc().update("INSERT INTO learning_blueprint(id,version,config_json,reviewer_id,created_at) VALUES(?,?,?,?,?)",blueprint.id(),blueprint.version(),db.encode(Map.of("cells",blueprint.cells())),reviewer,now());
        for(var row:db.rows("SELECT user_id FROM learning_profile"))event(((Number)row.get("userId")).longValue(),"blueprint:"+blueprint.id());
    }
    /** Called inside worker transaction. Full recomputation makes duplicate/out-of-order events harmless. */
    public void recompute(long owner) {
        lock(owner);var old=profile(owner);var attempts=records.selectList(new LambdaQueryWrapper<PracticeRecord>().eq(PracticeRecord::getUserId,owner)
            .eq(PracticeRecord::getGradingStatus,"valid").isNotNull(PracticeRecord::getIsCorrect));
        Map<Long,Integer> hints=new HashMap<>();for(var row:db.rows("SELECT i.record_id,i.hint_level FROM practice_session_item i JOIN practice_record r ON r.id=i.record_id WHERE r.user_id=?",owner))
            hints.put(((Number)row.get("recordId")).longValue(),((Number)row.get("hintLevel")).intValue());
        var next=engine.calculate(attempts.stream().map(r -> new LearningProfileEngine.Evidence(r,hints.get(r.getId()))).toList(),cells(),blueprintVersion(),old.revision()+1,now());
        var oldComparable=json.convertValue(old,new com.fasterxml.jackson.core.type.TypeReference<Map<String,Object>>(){});
        var nextComparable=json.convertValue(next,new com.fasterxml.jackson.core.type.TypeReference<Map<String,Object>>(){});
        for(String key:List.of("revision","updatedAt")) {oldComparable.remove(key);nextComparable.remove(key);}
        if(oldComparable.equals(nextComparable))return;
        db.jdbc().update("UPDATE learning_profile SET revision=?,data_json=?,updated_at=? WHERE user_id=?",next.revision(),db.encode(next),now(),owner);
        db.jdbc().update("INSERT INTO learning_profile_history(user_id,revision,data_json,created_at) VALUES(?,?,?,?)",owner,next.revision(),db.encode(next),now());
        var settings=db.one("SELECT * FROM learning_recommendation_settings WHERE user_id=? FOR UPDATE",owner);
        if(((Number)settings.get("enabled")).intValue()==0)return;
        Double last=settings.get("lastScore") instanceof Number n?n.doubleValue():null;
        boolean first=(settings.get("lastProfileRevision")==null||((Number)settings.get("lastProfileRevision")).intValue()==0)&&next.independentSamples()>0;
        boolean significant=last!=null&&next.referenceScore()!=null&&Math.abs(last-next.referenceScore())>=5;
        boolean sufficient=( ((Number)settings.get("lastSufficient")).intValue()==1)!=next.sufficient();
        boolean blueprintChanged=!old.blueprintVersion().equals(next.blueprintVersion());
        boolean invalidated=last!=null&&next.referenceScore()==null;
        if(blueprintChanged||invalidated) {
            db.jdbc().update("UPDATE learning_recommendation_settings SET pending_reason=?,not_before=?,pending_task_id=NULL,attempts=0 WHERE user_id=?",
                blueprintChanged?"BLUEPRINT_CHANGED":"EVIDENCE_INVALIDATED",now(),owner);
        } else if(first||significant||sufficient) {
            Object due=first?now():settings.get("lastCompletedAt")==null?now():java.time.LocalDateTime.parse(settings.get("lastCompletedAt").toString()).plusMinutes(30);
            db.jdbc().update("UPDATE learning_recommendation_settings SET pending_reason=COALESCE(pending_reason,?),not_before=COALESCE(not_before,?),attempts=0 WHERE user_id=?",first?"INITIAL_PROFILE":"ABILITY_CHANGED",due,owner);
        }
    }
    public Map<String,Object> history(long owner,int page,int size) {
        if(page<1||size<1||size>50)throw new ApiException(400,"分页参数无效");
        var list=db.rows("SELECT data_json FROM learning_profile_history WHERE user_id=? ORDER BY revision DESC LIMIT ? OFFSET ?",owner,size,(page-1)*size);
        return Map.of("list",list.stream().map(r -> r.get("data")).toList(),"total",db.jdbc().queryForObject("SELECT COUNT(*) FROM learning_profile_history WHERE user_id=?",Long.class,owner),"page",page,"size",size);
    }
    public Map<String,Object> snapshot(long owner) {
        var p=profile(owner);var result=new LinkedHashMap<String,Object>();result.put("profileRevision",p.revision());result.put("referenceScore",p.referenceScore());
        result.put("coverage",p.coverage());result.put("sufficient",p.sufficient());result.put("blueprintVersion",p.blueprintVersion());result.put("calibrated",false);return result;
    }
}
