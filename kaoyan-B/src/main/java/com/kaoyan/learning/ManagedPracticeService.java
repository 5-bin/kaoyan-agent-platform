package com.kaoyan.learning;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.kaoyan.common.ApiException;
import com.kaoyan.entity.*;
import com.kaoyan.mapper.*;
import com.kaoyan.service.*;
import com.kaoyan.learning.LearningContracts.*;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.transaction.annotation.Transactional;
import java.time.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

@Service
@RequiredArgsConstructor
@ConditionalOnProperty(name="kaoyan.learning.enabled", havingValue="true")
public class ManagedPracticeService {
    private final ChatRepository db;
    private final PracticeRecordMapper records;
    private final QuestionMapper questions;
    private final QuestionService questionService;
    private final UserQuestionMarkService marks;
    private final LearningProfiles profiles;
    private static final List<String> SUBJECTS=List.of("数据结构","计算机组成原理","操作系统","计算机网络");
    public static LocalDateTime now() { return LocalDateTime.now(ZoneId.of("Asia/Shanghai")); }
    public static String hash(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch(Exception e) { throw new IllegalStateException(e); }
    }
    static ApiException conflict(String text) { return new ApiException(409,text); }
    public boolean manages(long owner,String session) {
        return !db.rows("SELECT id FROM practice_session WHERE id=? AND user_id=?",session,owner).isEmpty();
    }
    private Map<String,Object> session(long owner,String id,boolean lock) {
        return db.one("SELECT * FROM practice_session WHERE id=? AND user_id=?"+(lock?" FOR UPDATE":""),id,owner);
    }
    private List<PracticeRecord> rows(long owner,String id) {
        return records.selectList(new LambdaQueryWrapper<PracticeRecord>().eq(PracticeRecord::getUserId,owner)
                .eq(PracticeRecord::getSessionId,id).orderByAsc(PracticeRecord::getOrderIndex));
    }
    private Map<String,Object> fixed(Question q) { return fixed(q,Map.of()); }
    private Map<String,Object> fixed(Question q,Map<String,Object> hints) {
        if (!QuestionHistoryView.playable(q)) throw conflict("题目已不可练习");
        var existing=db.rows("SELECT * FROM question_version WHERE question_id=? AND version=?",q.getId(),q.getVersion());
        if(!existing.isEmpty()) {
            if(((Number)existing.get(0).get("withdrawn")).intValue()==1) throw conflict("该题目版本已撤回");
            return db.object(existing.get(0).get("snapshot"));
        }
        var s=new LinkedHashMap<String,Object>();
        s.put("id",q.getId());s.put("version",q.getVersion());s.put("subject",q.getSubject());
        s.put("knowledgePoint",q.getKnowledgePoint());s.put("knowledgePointId",hash(q.getSubject()+":"+q.getKnowledgePoint()).substring(0,24));
        s.put("content",q.getContent());s.put("answer",q.getAnswer());s.put("analysis",q.getAnalysis());
        s.put("optionA",q.getOptionA());s.put("optionB",q.getOptionB());s.put("optionC",q.getOptionC());s.put("optionD",q.getOptionD());
        s.put("difficulty",q.getDifficulty());s.put("questionType",q.getQuestionType());s.put("snapshotAtCreation",true);
        s.put("sourceType",q.getSourceType());s.put("sourceName",q.getSourceName());s.put("sourceLocator",q.getSourceLocator());
        s.put("sourceYear",q.getSourceYear());s.put("sourceQuestionNo",q.getSourceQuestionNo());s.put("permissionNote",q.getPermissionNote());
        s.putAll(hints);
        db.jdbc().update("INSERT INTO question_version(question_id,version,snapshot_json,created_at) VALUES(?,?,?,?)",
                q.getId(),q.getVersion(),db.encode(s),now());return s;
    }
    @Transactional
    public void register(long owner,String id,String kind,Map<String,Object> blueprint) {
        profiles.ensure(owner);
        db.jdbc().update("INSERT INTO practice_session(id,user_id,kind,state,revision,current_index,blueprint_json,created_at) VALUES(?,?,?,'RUNNING',0,0,?,?)",
                id,owner,kind,db.encode(blueprint),now());
        for(var r:rows(owner,id).stream().sorted(Comparator.comparing(PracticeRecord::getQuestionId)).toList()) {
            Question q=questions.selectForUpdate(r.getQuestionId());
            if(q==null)throw conflict("题目已不可练习");
            if(r.getQuestionSnapshot()!=null && r.getQuestionSnapshot().get("version") instanceof Number n && n.intValue()!=q.getVersion())
                throw conflict("抽题期间题目版本已变化，请重新创建批次");
            r.setQuestionSnapshot(fixed(q));records.updateById(r);
            db.jdbc().update("INSERT INTO practice_session_item(record_id,session_id,hint_level) VALUES(?,?,0)",r.getId(),id);
        }
    }
    @Transactional
    public Map<String,Object> diagnose(long owner) {
        var selected=new ArrayList<Question>();var missing=new ArrayList<Map<String,Object>>();
        var cells=profiles.cells();
        if(cells.isEmpty()) {
            for(String subject:SUBJECTS)for(var part:Map.of("EASY",2,"MEDIUM",2,"HARD",1).entrySet())
                pick(selected,missing,subject,null,part.getKey(),part.getValue());
        } else for(var cell:cells)pick(selected,missing,cell.subject(),cell.knowledgePoint(),cell.difficulty(),cell.count());
        if(selected.isEmpty())throw new ApiException(409,"当前没有可用于诊断的审核题目");
        String id=com.kaoyan.util.IdUtil.managedSessionId();
        int index=0;
        for(var q:selected) {
            var r=new PracticeRecord();r.setUserId(owner);r.setSessionId(id);r.setQuestionId(q.getId());r.setOrderIndex(index++);
            r.setGradingStatus("valid");r.setQuestionSnapshot(Map.of("version",q.getVersion()));records.insert(r);
        }
        Map<String,Object> blueprint=Map.of("id",cells.isEmpty()?"diagnostic-prototype-v1":profiles.blueprintVersion(),"approved",!cells.isEmpty(),"expectedCount",cells.isEmpty()?20:cells.stream().mapToInt(Cell::count).sum(),"actualCount",selected.size(),"missing",missing);
        register(owner,id,"DIAGNOSTIC",blueprint);
        return Map.of("sessionId",id,"actualCount",selected.size(),"missing",missing,"blueprintVersion",blueprint.get("id"));
    }
    private void pick(List<Question> selected,List<Map<String,Object>> missing,String subject,String point,String difficulty,int count) {
        var query=new LambdaQueryWrapper<Question>().eq(Question::getSubject,subject).eq(Question::getDifficulty,difficulty)
            .eq(Question::getActive,1).eq(Question::getReviewStatus,"APPROVED").eq(Question::getQuestionType,"SINGLE_CHOICE");
        if(point!=null)query.eq(Question::getKnowledgePoint,point);
        var pool=questions.selectList(query.orderByAsc(Question::getStableOrder).orderByAsc(Question::getId));Collections.shuffle(pool);
        var picked=pool.stream().filter(q -> selected.stream().noneMatch(v -> v.getId().equals(q.getId())))
            .filter(q -> db.rows("SELECT question_id FROM question_version WHERE question_id=? AND version=? AND withdrawn=1",q.getId(),q.getVersion()).isEmpty()).limit(count).toList();
        selected.addAll(picked);
        if(picked.size()<count)missing.add(Map.of("subject",subject,"knowledgePoint",point==null?"全科":point,"difficulty",difficulty,"missing",count-picked.size()));
    }
    @Transactional
    public Map<String,Object> publishRevision(long id,Revision req,long reviewer) {
        var q=questions.selectForUpdate(id);if(q==null)throw new ApiException(404,"题目不存在");
        if(!"APPROVED".equals(q.getReviewStatus())||!Objects.equals(q.getVersion(),req.replacement().version()))throw conflict("请读取当前已审核题目版本再发布修订");
        // Archive first. Reuse the existing validated edit/review pipeline inside this transaction.
        if(!db.rows("SELECT question_id FROM question_version WHERE question_id=? AND version=?",id,q.getVersion()).isEmpty()) { /* already immutable, including withdrawn versions */ }
        else if(Integer.valueOf(1).equals(q.getActive()))fixed(q);
        else {
            q.setActive(1); // only the archive helper sees this; persisted availability stays unchanged.
            fixed(q);
        }
        q.setReviewStatus("PENDING_REVIEW");questions.updateById(q);
        var replacement=questionService.update(id,req.replacement());
        questionService.submitReview(id,reviewer,"APPROVED",req.reviewComment(),replacement.getVersion());
        var published=questions.selectForUpdate(id);published.setActive(1);questions.updateById(published);
        var hints=new LinkedHashMap<String,Object>();hints.put("hintConcept",req.hints().concept());hints.put("hintDirection",req.hints().direction());
        fixed(published,hints);
        return Map.of("questionId",id,"version",published.getVersion(),"reviewerUserId",reviewer);
    }
    public State state(long owner,String id) {
        var s=session(owner,id,false);boolean reveal=!"RUNNING".equals(s.get("state"));
        var items=new ArrayList<Item>();
        for(var r:rows(owner,id)) {
            var m=db.one("SELECT * FROM practice_session_item WHERE record_id=?",r.getId());var q=r.getQuestionSnapshot();
            boolean graded=reveal||!"DIAGNOSTIC".equals(s.get("kind"));boolean valid="valid".equals(r.getGradingStatus());
            items.add(new Item(r.getId(),r.getQuestionId(),r.getOrderIndex(),text(q,"subject"),text(q,"knowledgePoint"),text(q,"difficulty"),
                text(q,"content"),text(q,"optionA"),text(q,"optionB"),text(q,"optionC"),text(q,"optionD"),r.getUserAnswer(),
                (String)m.get("draftAnswer"),m.get("submittedAt")!=null,((Number)m.get("hintLevel")).intValue(),!valid,
                graded&&valid?r.getIsCorrect():null,graded&&valid&&r.getIsCorrect()!=null?text(q,"answer"):null,
                graded&&valid&&r.getIsCorrect()!=null?text(q,"analysis"):null));
        }
        return new State(id,(String)s.get("kind"),(String)s.get("state"),((Number)s.get("revision")).intValue(),
            ((Number)s.get("currentIndex")).intValue(),db.object(s.get("blueprint")),items);
    }
    @Transactional
    public State progress(long owner,String id,Progress req) {
        var s=session(owner,id,true);running(s);
        if(((Number)s.get("revision")).intValue()!=req.revision())throw conflict("草稿版本已变化，请重新读取后保存");
        var list=rows(owner,id);if(req.currentIndex()>=list.size())throw new ApiException(400,"题目位置无效");
        var byId=new HashMap<Long,PracticeRecord>();list.forEach(r -> byId.put(r.getId(),r));
        for(var e:req.answers().entrySet()) {
            var r=byId.get(e.getKey());if(r==null)throw new ApiException(404,"批次项目不存在");
            if(!"valid".equals(r.getGradingStatus()))throw conflict("题目已撤回");
            if(e.getValue()==null||!e.getValue().matches("[A-D]|"))throw new ApiException(400,"草稿选项无效");
            if(db.jdbc().update("UPDATE practice_session_item SET draft_answer=? WHERE record_id=? AND submitted_at IS NULL",e.getValue(),r.getId())!=1)
                throw conflict("该项目已提交，请重新读取");
        }
        db.jdbc().update("UPDATE practice_session SET revision=revision+1,current_index=? WHERE id=?",req.currentIndex(),id);
        return state(owner,id);
    }
    @Transactional
    public Submission submit(long owner,String id,long questionId,Long itemId,String requestId,String answer) {
        // The account row serializes request IDs across different sessions too.
        profiles.lock(owner);var s=session(owner,id,true);
        if(requestId==null||!requestId.matches("[A-Za-z0-9_-]{1,64}"))throw new ApiException(400,"新批次提交需要clientRequestId");
        String selected=answer==null?"":answer.trim().toUpperCase(Locale.ROOT);
        if(!selected.matches("[A-D]"))throw new ApiException(400,"请选择A至D");
        String fingerprint=hash(id+":"+questionId+":"+itemId+":"+selected);
        var prior=db.rows("SELECT * FROM practice_request WHERE user_id=? AND request_id=?",owner,requestId);
        if(!prior.isEmpty()) {
            if(!fingerprint.equals(prior.get(0).get("fingerprint")))throw conflict("同一请求编号不能用于不同内容");
            var response=db.object(prior.get(0).get("response"));
            return new Submission(questionId,((Number)response.get("itemId")).longValue(),selected,true,
                response.get("isCorrect") instanceof Number n?n.intValue():null,(String)response.get("answer"),(String)response.get("analysis"));
        }
        running(s);
        var r=rows(owner,id).stream().filter(x -> x.getQuestionId()==questionId&&(itemId==null||x.getId().equals(itemId))).findFirst().orElseThrow(() -> new ApiException(404,"批次项目不存在"));
        var meta=db.one("SELECT * FROM practice_session_item WHERE record_id=?",r.getId());
        if(meta.get("submittedAt")!=null)throw conflict("该题已提交");
        if(!"valid".equals(r.getGradingStatus()))throw conflict("该题目版本已撤回");
        var current=questions.selectForUpdate(questionId);
        if(!QuestionHistoryView.playable(current))throw conflict("题目已不可练习");
        var snapshot=r.getQuestionSnapshot();
        if(snapshot==null||!Objects.toString(text(snapshot,"answer"),"").matches("[A-D]")||text(snapshot,"option"+selected)==null)throw conflict("题目快照不完整");
        r.setUserAnswer(selected);
        if(!"DIAGNOSTIC".equals(s.get("kind")))grade(r);
        records.updateById(r);
        db.jdbc().update("UPDATE practice_session_item SET submitted_at=?,draft_answer=NULL WHERE record_id=?",now(),r.getId());
        db.jdbc().update("UPDATE practice_session SET revision=revision+1 WHERE id=?",id);
        var result=new Submission(questionId,r.getId(),selected,true,r.getIsCorrect(),r.getIsCorrect()!=null?text(snapshot,"answer"):null,r.getIsCorrect()!=null?text(snapshot,"analysis"):null);
        db.jdbc().update("INSERT INTO practice_request(user_id,request_id,fingerprint,response_json,created_at) VALUES(?,?,?,?,?)",owner,requestId,fingerprint,db.encode(result),now());
        var pending=db.rows("SELECT i.record_id FROM practice_session_item i JOIN practice_record r ON r.id=i.record_id WHERE i.session_id=? AND i.submitted_at IS NULL AND r.grading_status='valid'",id);
        if(pending.isEmpty())finish(owner,id);
        return result;
    }
    private void grade(PracticeRecord r) {
        r.setIsCorrect(Objects.equals(text(r.getQuestionSnapshot(),"answer"),r.getUserAnswer())?1:0);
        r.setAnsweredAt(now());if(r.getIsCorrect()==0)marks.markWrong(r.getUserId(),r.getQuestionId());
        profiles.event(r.getUserId(),"answer:"+r.getId());
    }
    @Transactional
    public Map<String,Object> finish(long owner,String id) {
        profiles.lock(owner);var s=session(owner,id,true);if(!"RUNNING".equals(s.get("state")))return result(owner,id);
        for(var r:rows(owner,id)) if("valid".equals(r.getGradingStatus())&&r.getUserAnswer()!=null&&r.getIsCorrect()==null) {grade(r);records.updateById(r);}
        db.jdbc().update("UPDATE practice_session SET state='FINISHED',revision=revision+1,finished_at=? WHERE id=?",now(),id);
        profiles.event(owner,"finish:"+id);return result(owner,id);
    }
    public Map<String,Object> result(long owner,String id) {
        var s=state(owner,id);var list=s.items();boolean hidden="DIAGNOSTIC".equals(s.kind())&&"RUNNING".equals(s.state());
        long answered=list.stream().filter(i -> i.submitted()&&!i.withdrawn()).count();
        long correct=list.stream().filter(i -> Integer.valueOf(1).equals(i.isCorrect())).count();
        long assisted=list.stream().filter(i -> i.submitted()&&!i.withdrawn()&&i.hintLevelUsed()>0).count();
        var result=new LinkedHashMap<String,Object>();result.put("session",s);result.put("total",list.size());result.put("answered",answered);
        result.put("withdrawn",list.stream().filter(Item::withdrawn).count());result.put("unanswered",list.stream().filter(i -> !i.submitted()&&!i.withdrawn()).count());
        result.put("correct",hidden?null:correct);result.put("accuracy",hidden||answered==0?null:(double)correct/answered);result.put("assisted",assisted);
        long independent=answered-assisted;long independentCorrect=list.stream().filter(i -> !i.withdrawn()&&i.hintLevelUsed()==0&&Integer.valueOf(1).equals(i.isCorrect())).count();
        result.put("independentAccuracy",hidden||independent==0?null:(double)independentCorrect/independent);
        boolean four=SUBJECTS.stream().allMatch(sub -> list.stream().anyMatch(i -> sub.equals(i.subject())&&!i.withdrawn()&&i.submitted()));
        long valid=list.stream().filter(i -> !i.withdrawn()).count();
        result.put("diagnosticReferenceScore",!hidden&&four&&valid>0&&"DIAGNOSTIC".equals(s.kind())?Math.round(1500.0*correct/valid)/10.0:null);
        result.put("notice","单选诊断参考分未经完整408试卷校准；局部诊断不输出完整参考分。");
        result.put("profilePending",!db.rows("SELECT id FROM learning_event WHERE user_id=? AND state IN ('PENDING','PROCESSING') AND attempts<3",owner).isEmpty());
        result.put("profileUpdateFailed",!db.rows("SELECT id FROM learning_event WHERE user_id=? AND state='PENDING' AND attempts>=3",owner).isEmpty());
        return result;
    }
    @Transactional
    public Map<String,Object> hint(long owner,String id,long itemId,int level) {
        var s=session(owner,id,true);running(s);if("DIAGNOSTIC".equals(s.get("kind")))throw conflict("诊断模式不提供提示");
        var r=rows(owner,id).stream().filter(x -> x.getId()==itemId).findFirst().orElseThrow(() -> new ApiException(404,"项目不存在"));
        var m=db.one("SELECT * FROM practice_session_item WHERE record_id=?",itemId);
        if(!"valid".equals(r.getGradingStatus())||m.get("submittedAt")!=null)throw conflict("该项目不可查看提示");
        int previous=((Number)m.get("hintLevel")).intValue();if(level<1||level>2||level>previous+1)throw new ApiException(400,"请依次查看两级提示");
        var text=r.getQuestionSnapshot().get(level==1?"hintConcept":"hintDirection");
        if(!(text instanceof String value)||value.isBlank())return Map.of("available",false,"hintLevelUsed",previous);
        db.jdbc().update("UPDATE practice_session_item SET hint_level=? WHERE record_id=?",Math.max(previous,level),itemId);
        return Map.of("available",true,"text",text,"hintLevelUsed",Math.max(previous,level));
    }
    @Transactional
    public void withdraw(long questionId,int version,String reason) {
        var owners=db.rows("SELECT DISTINCT user_id FROM practice_record WHERE question_id=?",questionId);
        // Consistent lock order: account/profile then session, matching answer submissions.
        owners.stream().map(r -> ((Number)r.get("userId")).longValue()).sorted().forEach(profiles::lock);
        var q=questions.selectForUpdate(questionId);
        if(q==null)throw new ApiException(404,"题目不存在");
        if(q.getVersion()==version)fixed(q);
        if(db.jdbc().update("UPDATE question_version SET withdrawn=1,withdrawal_reason=? WHERE question_id=? AND version=?",reason,questionId,version)!=1)
            throw new ApiException(404,"历史版本不存在");
        for(var row:db.rows("SELECT DISTINCT r.session_id,r.user_id FROM practice_record r JOIN practice_session s ON s.id=r.session_id WHERE r.question_id=?",questionId))session(((Number)row.get("userId")).longValue(),(String)row.get("sessionId"),true);
        var affected=new HashSet<Long>();
        for(var r:records.selectList(new LambdaQueryWrapper<PracticeRecord>().eq(PracticeRecord::getQuestionId,questionId)))
            if(r.getQuestionSnapshot()!=null&&r.getQuestionSnapshot().get("version") instanceof Number n&&n.intValue()==version) {
                r.setGradingStatus("withdrawn");records.updateById(r);affected.add(r.getUserId());
            }
        if(q.getVersion()==version) {q.setActive(0);questions.updateById(q);}
        for(long owner:affected) {
            profiles.event(owner,"withdraw:"+questionId+":"+version);
            long wrong=records.selectList(new LambdaQueryWrapper<PracticeRecord>().eq(PracticeRecord::getUserId,owner).eq(PracticeRecord::getQuestionId,questionId)
                .eq(PracticeRecord::getGradingStatus,"valid").eq(PracticeRecord::getIsCorrect,0)).size();
            db.jdbc().update("UPDATE user_question_mark SET is_wrong=?,wrong_count=? WHERE user_id=? AND question_id=?",wrong>0?1:0,wrong,owner,questionId);
        }
    }
    private static void running(Map<String,Object> session) { if(!"RUNNING".equals(session.get("state")))throw conflict("批次已经结束"); }
    static String text(Map<String,Object> map,String key) { return map==null?null:map.get(key) instanceof String text?text:null; }
}
