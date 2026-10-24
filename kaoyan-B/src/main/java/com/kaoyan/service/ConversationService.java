package com.kaoyan.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.common.ApiException;
import com.kaoyan.common.AgentValidationException;
import com.kaoyan.common.AgentValidationException.Code;
import com.kaoyan.config.AgentProperties;
import com.kaoyan.dto.agent.AgentResponse;
import com.kaoyan.entity.Task;
import com.kaoyan.mapper.TaskMapper;
import com.kaoyan.service.impl.TaskStore;
import com.kaoyan.service.impl.TaskServiceImpl;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import java.io.*;
import java.net.URI;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;

@Service
@RequiredArgsConstructor
@Slf4j
public class ConversationService {
    private final ChatRepository db;
    private final TransactionTemplate transactions;
    private final TaskStore tasks;
    private final TaskMapper taskMapper;
    private final AgentProperties properties;
    private final PersonalDocumentService documents;
    private final AssistantPrivacyService privacy;
    private final AssistantLearningService learning;
    private final ObjectMapper json;
    private final ReferenceSourcePolicy sourcePolicy;
    private final ExecutorService workers = new ThreadPoolExecutor(4,4,0,TimeUnit.SECONDS,
        new ArrayBlockingQueue<>(16), new ThreadPoolExecutor.AbortPolicy());
    private final ScheduledExecutorService timer = Executors.newSingleThreadScheduledExecutor();
    private final HttpClient http = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(5)).build();
    private final ConcurrentMap<String,Live> running = new ConcurrentHashMap<>();

    public record Send(String query, String clientRequestId, String documentId, Integer documentVersion, Map<String,Object> pageContext, String referenceTaskId) {
        public Send(String query,String clientRequestId,String documentId,Integer documentVersion) { this(query,clientRequestId,documentId,documentVersion,null,null); }
        public Send(String query,String clientRequestId,String documentId,Integer documentVersion,Map<String,Object> pageContext) { this(query,clientRequestId,documentId,documentVersion,pageContext,null); }
    }
    public record Retry(String clientRequestId) {}

    private static final class Live {
        final String taskId;
        final Map<String,String> draft = new LinkedHashMap<>();
        final List<SseEmitter> listeners = new ArrayList<>();
        long version, savedAt, savedVersion;
        boolean done;
        String stage="等待生成";
        Future<?> future;
        InputStream upstream;
        Thread worker;
        Live(String id) { taskId=id; }
    }

    @EventListener(ApplicationReadyEvent.class)
    public void recover() {
        transactions.executeWithoutResult(tx -> {
            db.jdbc().update("UPDATE task SET status='FAILED',error_message='服务重启，生成已中断',updated_at=CURRENT_TIMESTAMP WHERE id IN (SELECT task_id FROM chat_generation WHERE status='RUNNING')");
            db.jdbc().update("UPDATE chat_generation SET status='FAILED',active_conversation_id=NULL,draft_json='{}',error_message='服务重启，生成已中断',version=version+1,updated_at=CURRENT_TIMESTAMP WHERE status='RUNNING'");
        });
        timer.scheduleAtFixedRate(this::heartbeat,10,10,TimeUnit.SECONDS);
        timer.scheduleAtFixedRate(this::flushDrafts,500,500,TimeUnit.MILLISECONDS);
        cleanupExpired();
        timer.scheduleAtFixedRate(this::cleanupExpired,1,1,TimeUnit.HOURS);
    }

    @PreDestroy
    public void close() {
        running.values().forEach(live -> { synchronized(live) { closeUpstream(live); } });
        workers.shutdownNow(); timer.shutdownNow();
    }

    private Map<String,Object> conversation(Long owner,String id,boolean lock) {
        return db.one("SELECT * FROM chat_conversation WHERE id=? AND user_id=?"+(lock?" FOR UPDATE":""),id,owner);
    }

    public Map<String,Object> create(Long owner) {
        return transactions.execute(tx -> {
            db.one("SELECT id FROM `user` WHERE id=? FOR UPDATE",owner);
            var profile=db.one("SELECT target_school,target_major,exam_year FROM `user` WHERE id=?",owner);
            Map<String,Object> conditions=new LinkedHashMap<>();
            if(profile.get("examYear")!=null) conditions.put("examYear",profile.get("examYear"));
            if(profile.get("targetMajor") instanceof String major && major.matches("[0-9]{6}")) conditions.put("majorCodes",List.of(major));
            String id=UUID.randomUUID().toString();
            db.jdbc().update("INSERT INTO chat_conversation(id,user_id,title,conditions_json,profile_json) VALUES(?,?,?,?,?)",
                id,owner,"新会话",db.encode(conditions),"{}");
            return publicConversation(conversation(owner,id,false));
        });
    }

    private Map<String,Object> publicConversation(Map<String,Object> value) {
        Map<String,Object> out=new LinkedHashMap<>();
        for(String key:List.of("id","title","conditions","createdAt","updatedAt")) out.put(key,value.get(key));
        return out;
    }

    public Map<String,Object> list(Long owner,int page,int size) {
        cleanupOwner(owner);
        return db.page("SELECT id,title,conditions_json,created_at,updated_at FROM chat_conversation WHERE user_id=? ORDER BY updated_at DESC,id",
            "SELECT COUNT(*) FROM chat_conversation WHERE user_id=?",page,size,owner);
    }

    public Map<String,Object> messages(Long owner,String id,int page,int size) {
        cleanupOwner(owner);
        var conv=conversation(owner,id,false);
        var result=db.page("SELECT id,sequence_no,content,document_id,created_at FROM chat_message WHERE conversation_id=? AND user_id=? ORDER BY sequence_no DESC",
            "SELECT COUNT(*) FROM chat_message WHERE conversation_id=? AND user_id=?",page,size,id,owner);
        @SuppressWarnings("unchecked") var rows=(List<Map<String,Object>>)result.get("list");
        for(var row:rows) {
            var attempts=db.rows("SELECT task_id,attempt_no,status,version,stage,error_message,draft_json,result_json,created_at FROM chat_generation WHERE message_id=? AND user_id=? ORDER BY attempt_no",row.get("id"),owner);
            for(var attempt:attempts) refreshActions(owner,attempt);
            row.put("attempts",attempts);
        }
        Map<String,Object> out=new LinkedHashMap<>(result);
        out.put("conversation",publicConversation(conv));
        return out;
    }

    private void requestId(String id) {
        if(id==null || !id.matches("[A-Za-z0-9_-]{1,64}")) throw new ApiException(400,"请求编号格式不合法");
    }
    private String hash(Object value) {
        // An absent optional field must not invalidate a pre-upgrade retry.
        if(value instanceof Send send && send.referenceTaskId()==null) {
            var legacy=db.object(db.encode(value));legacy.remove("referenceTaskId");value=legacy;
        }
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(db.encode(value).getBytes(StandardCharsets.UTF_8))); }
        catch(Exception e) { throw new IllegalStateException(e); }
    }
    private Map<String,Object> replay(String conversationId,String requestId,String hash) {
        var existing=db.rows("SELECT task_id,message_id,request_hash FROM chat_generation WHERE conversation_id=? AND client_request_id=?",conversationId,requestId);
        if(existing.isEmpty()) return null;
        if(!hash.equals(existing.get(0).get("requestHash"))) throw new ApiException(409,"同一请求编号不能提交不同内容");
        return Map.of("taskId",existing.get(0).get("taskId"),"messageId",existing.get(0).get("messageId"),"replayed",true);
    }

    public Map<String,Object> send(Long owner,String id,Send input) {
        cleanupOwner(owner);
        if(input==null || input.query()==null || input.query().isBlank() || input.query().strip().length()>8000)
            throw new ApiException(400,"问题长度需为1—8000字符");
        requestId(input.clientRequestId());
        Map<String,Object> settings=privacy.settings(owner);
        Map<String,Object> page=validatePage(input.pageContext());
        String fingerprint=hash(input);
        var result=transactions.execute(tx -> {
            db.one("SELECT id FROM `user` WHERE id=? FOR UPDATE",owner);
            var conv=conversation(owner,id,true);
            var previous=replay(id,input.clientRequestId(),fingerprint);
            if(previous!=null) return previous;
            ensureIdle(id);
            if(input.referenceTaskId()!=null) {
                requestId(input.referenceTaskId());
                db.one("SELECT task_id FROM chat_generation WHERE task_id=? AND conversation_id=? AND user_id=? AND status='SUCCESS' AND created_at>=?",
                    input.referenceTaskId(),id,owner,cutoff());
            }
            Map<String,Object> document=null;
            if(input.documentId()!=null) {
                document=documents.get(owner,input.documentId());
                if(input.documentVersion()==null || ((Number)document.get("version")).intValue()!=input.documentVersion())
                    throw new ApiException(409,"选中的笔记版本已变化，请重新读取");
            }
            String messageId=UUID.randomUUID().toString();
            int sequence=((Number)conv.get("nextSequence")).intValue();
            db.jdbc().update("INSERT INTO chat_message(id,conversation_id,user_id,sequence_no,content,document_id) VALUES(?,?,?,?,?,?)",
                messageId,id,owner,sequence,input.query().strip(),input.documentId());
            db.jdbc().update("UPDATE chat_conversation SET title=CASE WHEN next_sequence=1 THEN ? ELSE title END,next_sequence=next_sequence+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                input.query().strip().substring(0,Math.min(40,input.query().strip().length())),id);
            var context=context(owner,conv,sequence,input.query().strip(),document,settings);
            context.put("_pageContext",page);
            if(input.referenceTaskId()!=null) context.put("_referenceTaskId",input.referenceTaskId());
            return reserve(owner,id,messageId,1,input.clientRequestId(),fingerprint,context);
        });
        dispatch(result);
        return result;
    }

    private void ensureIdle(String id) {
        if(!db.rows("SELECT task_id FROM chat_generation WHERE active_conversation_id=?",id).isEmpty())
            throw new ApiException(409,"当前会话仍在生成，请先停止或等待完成");
    }

    public Map<String,Object> retry(Long owner,String id,String messageId,Retry input) {
        cleanupOwner(owner);
        Map<String,Object> settings=privacy.settings(owner);
        if(input==null) throw new ApiException(400,"缺少请求编号");
        requestId(input.clientRequestId());
        String fingerprint=hash(Map.of("retry",messageId));
        var result=transactions.execute(tx -> {
            db.one("SELECT id FROM `user` WHERE id=? FOR UPDATE",owner);
            var conv=conversation(owner,id,true);
            var previous=replay(id,input.clientRequestId(),fingerprint);
            if(previous!=null) return previous;
            ensureIdle(id);
            var message=db.one("SELECT * FROM chat_message WHERE id=? AND conversation_id=? AND user_id=?",messageId,id,owner);
            if(((Number)message.get("sequenceNo")).intValue()!=((Number)conv.get("nextSequence")).intValue()-1)
                throw new ApiException(409,"仅能重试最后一条问题");
            var last=db.one("SELECT * FROM chat_generation WHERE message_id=? ORDER BY attempt_no DESC LIMIT 1",messageId);
            var lastResult=db.object(last.get("result"));
            boolean retrySearch="SUCCESS".equals(last.get("status")) && "UNSUPPORTED".equals(lastResult.get("outcome"))
                && Set.of("BUILDING","BUSY","FAILED","UNAVAILABLE").contains(Objects.toString(lastResult.get("retrievalStatus"),""));
            if(!retrySearch&&!Set.of("FAILED","CANCELLED").contains(last.get("status"))) throw new ApiException(409,"仅失败、停止或题目检索尚未就绪的问题可以重试");
            var original=db.object(last.get("context"));
            Map<String,Object> document=null;
            var selected=db.object(original.get("document"));
            if(selected.get("id")!=null) {
                document=documents.get(owner,selected.get("id").toString());
                if(!Objects.equals(document.get("version"),selected.get("version"))) throw new ApiException(409,"笔记版本已变化，请重新提问");
            }
            var context=context(owner,conv,((Number)message.get("sequenceNo")).intValue(),Objects.toString(message.get("content")),document,settings);
            context.put("_pageContext",original.getOrDefault("_pageContext",Map.of()));
            if(original.get("_referenceTaskId")!=null) context.put("_referenceTaskId",original.get("_referenceTaskId"));
            return reserve(owner,id,messageId,((Number)last.get("attemptNo")).intValue()+1,input.clientRequestId(),fingerprint,context);
        });
        dispatch(result); return result;
    }

    private Map<String,Object> reserve(Long owner,String id,String messageId,int attempt,String requestId,String fingerprint,Map<String,Object> context) {
        // Serialize with other task entrypoints for this account; never hold this transaction during model IO.
        Task task=new Task(); task.setId(UUID.randomUUID().toString()); task.setUserId(owner);
        task.setTaskType("CHAT"); task.setStatus("RUNNING"); task.setInputPayload(Map.of("conversationId",id));
        tasks.begin(task);
        context.put("taskId",task.getId());
        db.jdbc().update("INSERT INTO chat_generation(task_id,conversation_id,message_id,user_id,attempt_no,client_request_id,request_hash,status,active_conversation_id,context_json,draft_json) VALUES(?,?,?,?,?,?,?,'RUNNING',?,?,?)",
            task.getId(),id,messageId,owner,attempt,requestId,fingerprint,id,db.encode(context),"{}");
        return Map.of("taskId",task.getId(),"messageId",messageId,"replayed",false);
    }

    private String excerpt(Object content) {
        String text=Objects.toString(content,"");
        return text.length()>3900 ? text.substring(0,3900)+"\n[历史内容节选，完整内容保存在会话中]" : text;
    }
    private Map<String,Object> context(Long owner,Map<String,Object> conv,int sequence,String query,Map<String,Object> document,Map<String,Object> settings) {
        var rows=db.rows("SELECT m.id,g.task_id,g.result_json FROM chat_message m JOIN chat_generation g ON g.message_id=m.id AND g.status='SUCCESS' WHERE m.conversation_id=? AND m.sequence_no<? AND m.created_at>=? ORDER BY m.sequence_no DESC LIMIT 3",conv.get("id"),sequence,cutoff());
        Collections.reverse(rows);
        List<Object> history=new ArrayList<>();
        for(var row:rows) {
            var result=db.object(row.get("result"));
            Object scopes=result.get("dataScopes");
            // Legacy history did not record categories: do not forward it to a provider.
            if(!(scopes instanceof List<?> used) || !((List<?>)settings.get("scopes")).containsAll(used)) continue;
            history.add(Map.of("messageId",row.get("id"),"taskId",row.get("taskId"),"scopes",scopes));
        }
        Map<String,Object> request=new LinkedHashMap<>();
        request.put("userId",owner); request.put("taskType","CHAT"); request.put("userInput",query);
        // References, not copied historical prose: expiry of an older turn cannot be extended by a newer snapshot.
        request.put("_historyRefs",history);
        request.put("profile",db.one("SELECT target_school,target_major,exam_year FROM `user` WHERE id=?",owner));
        request.put("conditions",conv.get("conditions"));
        request.put("privacy",privacy.wire(settings));
        request.put("_grant",com.kaoyan.security.UserContext.sessionGrant());
        request.put("_provider",settings.get("provider"));
        if(document!=null) {
            Map<String,Object> selected=new LinkedHashMap<>();
            for(String key:List.of("id","version","title","content")) selected.put(key,document.get(key));
            request.put("document",selected);
        }
        return request;
    }

    private void dispatch(Map<String,Object> result) {
        if(Boolean.TRUE.equals(result.get("replayed"))) return;
        String id=result.get("taskId").toString();
        Live live=running.computeIfAbsent(id,Live::new);
        try {
            synchronized(live) {
                if(live.done || !"RUNNING".equals(snapshot(id).get("status"))) { running.remove(id,live); return; }
                live.future=workers.submit(() -> generate(live));
            }
            timer.schedule(() -> terminate(live,"FAILED","生成超时，请重试",null),48,TimeUnit.SECONDS);
        } catch(RejectedExecutionException e) { terminate(live,"FAILED","生成服务繁忙，请稍后重试",null); }
    }

    private void generate(Live live) {
        Code failureCode = Code.UNEXPECTED_ERROR;
        try {
            synchronized(live) { if(live.done) return; live.worker=Thread.currentThread(); }
            var saved=db.one("SELECT user_id,conversation_id,context_json FROM chat_generation WHERE task_id=?",live.taskId);
            Long owner=((Number)saved.get("userId")).longValue();
            var context=db.object(saved.get("context"));
            checkAuthorization(owner,context,true);
            Map<String,Object> planRequest=wireContext(context);
            var page=db.object(context.get("_pageContext"));
            Map<String,Object> publicPage=new LinkedHashMap<>();
            for(String key:List.of("page","subject","from","to")) if(page.get(key)!=null) publicPage.put(key,page.get(key));
            if(!publicPage.isEmpty()) planRequest.put("pageContext",publicPage);
            failureCode = Code.UPSTREAM_FAILED;
            var planned=http.send(HttpRequest.newBuilder(URI.create(properties.getBaseUrl()+"/internal/rag/conversation/plan"))
                .timeout(Duration.ofSeconds(22)).header("Content-Type","application/json").header("X-Internal-Key",properties.getInternalKey())
                .POST(HttpRequest.BodyPublishers.ofString(db.encode(planRequest))).build(),HttpResponse.BodyHandlers.ofString());
            if(planned.statusCode()!=200 || planned.body().length()>40000) throw new IOException("plan_failed");
            failureCode = Code.PLAN_VALIDATION_FAILED;
            var plan=db.object(planned.body());
            validatePlan(plan,Objects.toString(context.get("userInput")));
            failureCode = Code.UNEXPECTED_ERROR;
            page=resolveTargets(owner,saved.get("conversationId").toString(),plan,page,Objects.toString(context.get("_referenceTaskId"),null),context);
            context.put("_pageContext",page);
            if(plan.get("clarification")!=null) {
                plan.put("reads",List.of());plan.put("operation","NONE");plan.put("target","selected");
                plan.put("ordinal",null);plan.put("questionRefs",List.of());page=Map.of();
                context.put("_pageContext",page);
            }
            checkAuthorization(owner,context,true);
            var data=learning.read(owner,plan,page);
            var storedPlan=new LinkedHashMap<>(plan);
            storedPlan.put("standaloneQuery",context.get("userInput"));
            context.put("preparedPlan",storedPlan); context.put("_learning",data);
            synchronized(live) {
                if(live.done) return;
                int changed=db.jdbc().update("UPDATE chat_generation SET context_json=? WHERE task_id=? AND status='RUNNING'",db.encode(context),live.taskId);
                if(changed!=1) return;
            }
            checkAuthorization(owner,context,true);
            var streamContext=wireContext(context);
            streamContext.put("preparedPlan",plan); // Expanded historical query exists only for this live request.
            failureCode = Code.UPSTREAM_FAILED;
            var request=HttpRequest.newBuilder(URI.create(properties.getBaseUrl()+"/internal/rag/conversation/stream"))
                .timeout(Duration.ofSeconds(47)).header("Content-Type","application/json")
                .header("X-Internal-Key",properties.getInternalKey()).POST(HttpRequest.BodyPublishers.ofString(db.encode(streamContext))).build();
            var response=http.send(request,HttpResponse.BodyHandlers.ofInputStream());
            synchronized(live) {
                if(live.done) { response.body().close(); return; }
                live.upstream=response.body();
            }
            if(response.statusCode()!=200) throw new IOException("upstream_status");
            try(var reader=new BufferedReader(new InputStreamReader(response.body(),StandardCharsets.UTF_8))) {
                String line;
                while((line=reader.readLine())!=null) {
                    if(line.length()>200000) throw new IOException("upstream_frame_limit");
                    if(!line.startsWith("data: ")) continue;
                    var event=db.object(line.substring(6));
                    if("result".equals(event.get("type"))) {
                        failureCode = Code.RESULT_VALIDATION_FAILED;
                        AgentResponse result=json.convertValue(event.get("response"),AgentResponse.class);
                        Task task=new Task(); task.setId(live.taskId); task.setTaskType("CHAT");
                        TaskServiceImpl.validateResponse(task,result);
                        if(!"SUCCESS".equals(result.getStatus())) {
                            failureCode = Code.UPSTREAM_FAILED;
                            throw new IOException("upstream_failed");
                        }
                        sourcePolicy.validateResponse(result);
                        var output=db.object(result.getResult()); output.put("references",result.getReferences());
                        failureCode = Code.CONDITIONS_VALIDATION_FAILED;
                        validateConditions(db.object(output.get("conditions")));
                        failureCode = Code.DOCUMENT_VALIDATION_FAILED;
                        validateProposal(output,context);
                        failureCode = Code.UNEXPECTED_ERROR;
                        output.put("evidence",data.getOrDefault("evidence",List.of()));
                        if(data.get("retrievalStatus")!=null)output.put("retrievalStatus",data.get("retrievalStatus"));
                        else output.remove("retrievalStatus");
                        output.put("dataScopes",dataScopes(context,data));
                        output.put("readScope",data.getOrDefault("scope",List.of()));
                        output.put("standaloneQuery",context.get("userInput"));
                        output.remove("actions"); // Only Java can issue and execute business actions.
                        terminate(live,"SUCCESS",null,output); return;
                    }
                    if("error".equals(event.get("type"))) throw new IOException("upstream_failed");
                    progress(live,event);
                }
            }
            throw new IOException("upstream_incomplete");
        } catch(Exception error) {
            Code code = error instanceof AgentValidationException validation ? validation.getCode() : failureCode;
            log.warn("task={} chatFailure={} errorCode={}",live.taskId,error.getClass().getSimpleName(),code.name());
            terminate(live,"FAILED","生成失败或输出未通过校验，请重试",null);
        }
    }

    private void validateConditions(Map<String,Object> conditions) {
        if(!Set.of("examYear","majorCodes","degreeType","regions","regionConstraint","studyMode","examSubjects","explainWithAi").containsAll(conditions.keySet()))
            throw new IllegalStateException("invalid_conditions");
        Object year=conditions.get("examYear");
        if(year!=null && (!(year instanceof Number n) || n.intValue()<2000 || n.intValue()>2100)) throw new IllegalStateException("invalid_year");
        for(var rule:Map.of("degreeType",Set.of("academic","professional"),"regionConstraint",Set.of("required","preferred"),"studyMode",Set.of("full_time","part_time")).entrySet())
            if(conditions.get(rule.getKey())!=null && !rule.getValue().contains(conditions.get(rule.getKey()))) throw new IllegalStateException("invalid_condition_enum");
        for(String key:List.of("majorCodes","regions","examSubjects")) {
            Object value=conditions.get(key); if(value==null) continue;
            int max=key.equals("regions")?30:key.equals("majorCodes")?10:4;
            if(!(value instanceof List<?> list) || list.size()>max) throw new IllegalStateException("invalid_condition_list");
            for(Object item:list) if(!(item instanceof String s) || s.isBlank() || s.length()>50
                || key.equals("majorCodes")&&!s.matches("[0-9]{6}") || key.equals("examSubjects")&&!s.matches("[0-9]{3}")) throw new IllegalStateException("invalid_condition_item");
        }
        if(conditions.get("explainWithAi")!=null && !(conditions.get("explainWithAi") instanceof Boolean)) throw new IllegalStateException("invalid_boolean");
    }

    private void validateProposal(Map<String,Object> result,Map<String,Object> context) {
        if(result.get("documentProposal")==null) return;
        var proposal=db.object(result.get("documentProposal"));
        if(!(proposal.get("title") instanceof String title) || title.isBlank() || title.length()>100
            || !(proposal.get("content") instanceof String content) || content.isBlank() || content.length()>40000) throw new IllegalStateException("invalid_document");
        if("update".equals(proposal.get("operation"))) {
            var selected=db.object(context.get("document"));
            if(!Objects.equals(selected.get("id"),proposal.get("documentId"))
                || !Objects.equals(selected.get("version"),proposal.get("baseVersion"))) throw new IllegalStateException("invalid_document_target");
        } else if(!"create".equals(proposal.get("operation")) || proposal.get("documentId")!=null || proposal.get("baseVersion")!=null)
            throw new IllegalStateException("invalid_document_operation");
    }

    private void progress(Live live,Map<String,Object> event) {
        synchronized(live) {
            if(live.done) return;
            var saved=db.one("SELECT user_id,context_json FROM chat_generation WHERE task_id=?",live.taskId);
            checkAuthorization(((Number)saved.get("userId")).longValue(),db.object(saved.get("context")),false);
            if("stage".equals(event.get("type"))) live.stage=Objects.toString(event.get("stage"),"生成中");
            else if("delta".equals(event.get("type"))) {
                String slot=Objects.toString(event.get("slot"),"");
                if(!slot.matches("answer|content|summary|candidate\\.[0-4]")) throw new IllegalStateException("invalid_projection");
                String old=live.draft.getOrDefault(slot,"");
                // Python offsets count Unicode code points, unlike Java String.length().
                if(!(event.get("offset") instanceof Number offset) || offset.intValue()!=old.codePointCount(0,old.length())) throw new IllegalStateException("invalid_offset");
                String next=old+Objects.toString(event.get("text"),"");
                if(next.length()>50000) throw new IllegalStateException("draft_limit");
                live.draft.put(slot,next);
            } else return;
            live.version++;
            if(System.currentTimeMillis()-live.savedAt>500) {
                db.jdbc().update("UPDATE chat_generation SET draft_json=?,version=?,stage=?,updated_at=CURRENT_TIMESTAMP WHERE task_id=? AND status='RUNNING'",db.encode(live.draft),live.version,live.stage,live.taskId);
                live.savedAt=System.currentTimeMillis();
                live.savedVersion=live.version;
            }
            Map<String,Object> value=new LinkedHashMap<>(event);
            value.put("taskId",live.taskId); value.put("version",live.version);
            broadcast(live,Objects.toString(event.get("type")),value);
        }
    }

    private void terminate(Live live,String status,String error,Map<String,Object> result) {
        synchronized(live) {
            if(live.done) return;
            long version=live.version+1;
            Boolean won=transactions.execute(tx -> {
                Map<String,Object> saved=null;
                if(result!=null) {
                    saved=db.one("SELECT user_id,conversation_id,context_json FROM chat_generation WHERE task_id=?",live.taskId);
                    checkAuthorization(((Number)saved.get("userId")).longValue(),db.object(saved.get("context")),false);
                    db.one("SELECT task_id FROM chat_generation WHERE task_id=? FOR UPDATE",live.taskId);
                }
                int changed=db.jdbc().update("UPDATE chat_generation SET status=?,active_conversation_id=NULL,draft_json='{}',result_json=?,version=?,error_message=?,updated_at=CURRENT_TIMESTAMP WHERE task_id=? AND status='RUNNING'",
                    status,result==null?null:db.encode(result),version,error,live.taskId);
                if(changed!=1) return false;
                db.jdbc().update("UPDATE task SET status=?,result_payload=?,release_id=?,error_message=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='RUNNING'",
                    status,result==null?null:db.encode(result),result==null?null:result.get("releaseId"),error,live.taskId);
                if(result!=null) db.jdbc().update("UPDATE chat_conversation SET conditions_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=(SELECT conversation_id FROM chat_generation WHERE task_id=?)",db.encode(result.get("conditions")),live.taskId);
                if(result!=null && saved!=null) {
                    var context=db.object(saved.get("context"));
                    var actions=learning.finalizeActions(((Number)saved.get("userId")).longValue(),saved.get("conversationId").toString(),live.taskId,
                        db.object(context.get("preparedPlan")),db.object(context.get("_pageContext")),db.object(context.get("_learning")));
                    result.put("actions",actions);
                    String operation=Objects.toString(db.object(context.get("preparedPlan")).get("operation"),"NONE");
                    if(!actions.isEmpty()) {
                        var action=actions.get(0);
                        if("FAVORITE_ADD".equals(operation)&&"SUCCESS".equals(action.get("status")))
                            result.put("answer","已加入收藏。题目与执行结果见下方操作记录；重复收藏不会重复添加。");
                        else {
                            String message="已找到符合条件的题目，请核对下方题目并确认操作。";
                            Object total=db.object(context.get("_learning")).get("total");
                            if(total instanceof Number n && n.intValue()>50 && !"PRACTICE_CREATE".equals(operation))
                                message+="共匹配"+n.intValue()+"题，本次仅预览前50题，另有"+(n.intValue()-50)+"题未纳入；请缩小范围后处理其余题目。";
                            result.put("answer",message);
                        }
                        result.put("outcome","COMPLETED");
                    } else if(!"NONE".equals(operation) && !Set.of("BUILDING","BUSY","FAILED","UNAVAILABLE").contains(Objects.toString(db.object(context.get("_learning")).get("retrievalStatus"),""))) {
                        result.put("answer","当前筛选条件下没有可操作的题目，未创建练习或修改记录。请调整知识点或选择题目。\n推荐问法：将我的错题本中涉及 TCP 的题目加入收藏；也可先查看错题本确认主题，再说：收藏 Q1。 ");
                        result.put("outcome","NEEDS_INPUT");
                    }
                    db.jdbc().update("UPDATE chat_generation SET result_json=? WHERE task_id=?",db.encode(result),live.taskId);
                    db.jdbc().update("UPDATE task SET result_payload=? WHERE id=?",db.encode(result),live.taskId);
                }
                return true;
            });
            if(!Boolean.TRUE.equals(won)) {
                live.done=true; live.draft.clear(); closeUpstream(live);
                live.listeners.forEach(SseEmitter::complete); live.listeners.clear(); running.remove(live.taskId,live); return;
            }
            live.done=true; live.version=version; live.draft.clear();
            closeUpstream(live);
            Map<String,Object> snapshot=snapshot(live.taskId);
            broadcast(live,status.equals("SUCCESS")?"completed":status.equals("CANCELLED")?"cancelled":"failed",snapshot);
            live.listeners.forEach(SseEmitter::complete); live.listeners.clear();
            running.remove(live.taskId,live);
        }
    }

    private void closeUpstream(Live live) {
        if(live.upstream!=null) try { live.upstream.close(); } catch(IOException ignored) {}
        if(live.future!=null && live.worker!=Thread.currentThread()) live.future.cancel(true);
    }
    private Map<String,Object> snapshot(String taskId) {
        var out=db.one("SELECT task_id,user_id,message_id,attempt_no,status,version,stage,error_message,draft_json,result_json FROM chat_generation WHERE task_id=?",taskId);
        Long owner=((Number)out.remove("userId")).longValue();
        refreshActions(owner,out);
        return out;
    }
    private void emit(SseEmitter listener,String type,Object value) throws IOException {
        listener.send(SseEmitter.event().name(type).data(value));
    }
    private void broadcast(Live live,String type,Object value) {
        live.listeners.removeIf(listener -> { try { emit(listener,type,value); return false; } catch(Exception error) { listener.complete(); return true; } });
    }
    private void heartbeat() {
        for(Live live:running.values()) synchronized(live) {
            try {
                var saved=db.one("SELECT user_id,context_json FROM chat_generation WHERE task_id=?",live.taskId);
                checkAuthorization(((Number)saved.get("userId")).longValue(),db.object(saved.get("context")),false);
            } catch(Exception e) { terminate(live,"CANCELLED","登录或授权已变化，生成已停止",null); continue; }
            live.listeners.removeIf(listener -> { try { listener.send(SseEmitter.event().comment("heartbeat")); return false; } catch(Exception e) { listener.complete(); return true; } });
        }
    }

    private void flushDrafts() {
        for(Live live:running.values()) synchronized(live) {
            if(live.done || live.savedVersion==live.version) continue;
            try {
                db.jdbc().update("UPDATE chat_generation SET draft_json=?,version=?,stage=?,updated_at=CURRENT_TIMESTAMP WHERE task_id=? AND status='RUNNING'",db.encode(live.draft),live.version,live.stage,live.taskId);
                live.savedAt=System.currentTimeMillis(); live.savedVersion=live.version;
            } catch(Exception error) { log.warn("task={} draftSaveFailure={}",live.taskId,error.getClass().getSimpleName()); }
        }
    }

    public SseEmitter subscribe(Long owner,String id,String taskId) {
        cleanupOwner(owner);
        conversation(owner,id,false);
        db.one("SELECT task_id FROM chat_generation WHERE task_id=? AND conversation_id=? AND user_id=?",taskId,id,owner);
        SseEmitter emitter=new SseEmitter(65000L);
        Live live=running.get(taskId);
        Runnable detach=() -> { if(live!=null) synchronized(live) { live.listeners.remove(emitter); } };
        emitter.onCompletion(detach); emitter.onTimeout(() -> { detach.run(); emitter.complete(); }); emitter.onError(error -> detach.run());
        try {
            if(live!=null) synchronized(live) {
                var value=snapshot(taskId);
                value.put("draft",new LinkedHashMap<>(live.draft)); value.put("version",live.version); value.put("stage",live.stage);
                emit(emitter,"snapshot",value);
                if(!live.done) live.listeners.add(emitter); else emitter.complete();
            } else { emit(emitter,"snapshot",snapshot(taskId)); emitter.complete(); }
        } catch(IOException e) { emitter.completeWithError(e); }
        return emitter;
    }

    public Map<String,Object> cancel(Long owner,String id,String taskId) {
        conversation(owner,id,false);
        db.one("SELECT task_id FROM chat_generation WHERE task_id=? AND conversation_id=? AND user_id=?",taskId,id,owner);
        Live live=running.computeIfAbsent(taskId,Live::new);
        if("RUNNING".equals(snapshot(taskId).get("status"))) terminate(live,"CANCELLED","已停止生成，可以重试",null);
        else running.remove(taskId,live);
        return snapshot(taskId);
    }

    public Map<String,Object> apply(Long owner,String id,String taskId,PersonalDocumentService.Save input) {
        cleanupOwner(owner);
        return transactions.execute(tx -> {
            conversation(owner,id,false);
            var generation=db.one("SELECT * FROM chat_generation WHERE task_id=? AND conversation_id=? AND user_id=? FOR UPDATE",taskId,id,owner);
            if(!"SUCCESS".equals(generation.get("status"))) throw new ApiException(409,"生成尚未成功，无法保存笔记");
            var result=db.object(generation.get("result"));
            if(result.get("documentProposal")==null) throw new ApiException(409,"该回复没有笔记建议");
            var proposal=db.object(result.get("documentProposal"));
            Integer base=proposal.get("baseVersion") instanceof Number n?n.intValue():null;
            var save=new PersonalDocumentService.Save(input==null?Objects.toString(proposal.get("title")):input.title(),
                input==null?Objects.toString(proposal.get("content")):input.content(),base);
            return documents.save(owner,(String)proposal.get("documentId"),save,taskId);
        });
    }

    private Map<String,Object> validatePage(Map<String,Object> page) {
        if(page==null) return new LinkedHashMap<>();
        if(!Set.of("page","subject","from","to","sessionId","documentId","selectedQuestionIds","visibleQuestionIds").containsAll(page.keySet())
            || !Set.of("wrong","favorite","stat","documents","practice","notes").contains(page.get("page"))) throw new ApiException(400,"页面上下文不合法");
        for(String key:List.of("selectedQuestionIds","visibleQuestionIds")) if(page.containsKey(key)) {
            if(!(page.get(key) instanceof List<?> list) || list.size()>50 || list.stream().anyMatch(id -> !(id instanceof Number n) || n.longValue()<=0 || n.doubleValue()!=n.longValue()))
                throw new ApiException(400,"所选题目编号不合法");
        }
        if(page.get("documentId")!=null && (!(page.get("documentId") instanceof Number n) || n.longValue()<=0 || n.doubleValue()!=n.longValue()))
            throw new ApiException(400,"资料编号不合法");
        for(String key:List.of("subject","from","to","sessionId")) if(page.get(key)!=null && (!(page.get(key) instanceof String s) || s.length()>100))
            throw new ApiException(400,"页面筛选不合法");
        return new LinkedHashMap<>(page);
    }

    private void validatePlan(Map<String,Object> plan,String query) {
        if(!Set.of("KNOWLEDGE_QA","SCHOOL_RECOMMEND","DOCUMENT_CREATE","DOCUMENT_UPDATE","CHAT","LEARNING_ANALYSIS").contains(plan.get("action")))
            throw new IllegalStateException("invalid_plan");
        if(!(plan.get("reads") instanceof List<?> reads) || reads.size()>6 || !Set.of("wrong","favorite","stats","practice","documents","questions").containsAll(reads))
            throw new IllegalStateException("invalid_reads");
        String op=Objects.toString(plan.get("operation"),"NONE");
        if(!Set.of("NONE","FAVORITE_ADD","FAVORITE_REMOVE","WRONG_REMOVE","PRACTICE_CREATE").contains(op)) throw new IllegalStateException("invalid_operation");
        // A model plan never makes quoted instructions or a previous answer an authorization.
        boolean requested=switch(op) {
            case "FAVORITE_ADD" -> query.matches("(?s).*(收藏|收录|保存这.*题).*") && !query.matches("(?s).*(取消|不要|别收藏|如何|怎么|能否|可以吗|是否).*");
            case "FAVORITE_REMOVE" -> query.matches("(?s).*((取消|移出|移除|删除).{0,12}收藏|收藏.{0,12}(取消|移出|移除|删除)).*");
            case "WRONG_REMOVE" -> query.matches("(?s).*((移出|删除|移除|取消).{0,12}错题|错题.{0,12}(移出|删除|移除|取消)).*");
            case "PRACTICE_CREATE" -> query.matches("(?s).*(创建|安排|开始|生成|来|练习|重练).*");
            default -> true;
        };
        if(!requested || query.matches("(?s).*(不要|不想|别|不要执行|仅分析|只分析).*") || plan.get("clarification")!=null) plan.put("operation","NONE");
        if(!(plan.get("count") instanceof Number count) || count.intValue()<1 || count.intValue()>50) throw new IllegalStateException("invalid_count");
        if(!Set.of("selected","visible","wrong","favorite","normal").contains(plan.get("target"))) throw new IllegalStateException("invalid_target");
        if(plan.get("knowledgePoint")!=null && (!(plan.get("knowledgePoint") instanceof String point)||point.isBlank()||point.length()>255))
            throw new IllegalStateException("invalid_knowledge_point");
    }

    private Map<String,Object> wireContext(Map<String,Object> context) {
        Map<String,Object> out=new LinkedHashMap<>();
        for(String key:List.of("taskId","userId","taskType","userInput","messages","profile","conditions","document","privacy","preparedPlan","learningContext"))
            if(context.containsKey(key)) out.put(key,context.get(key));
        out.put("quotaExempt",tasks.isQuotaExempt(((Number)context.get("userId")).longValue()));
        if(context.get("_learning")!=null) out.put("learningContext",privacy.project(context.get("_learning")));
        if(context.get("_referenceScopes") instanceof List<?> derived) {
            var grant=db.object(out.get("privacy"));
            if(!(grant.get("scopes") instanceof List<?> allowed) || !allowed.containsAll(derived)) {
                // A public excerpt selected using a private topic inherits that
                // topic's sensitivity, even after its original scope is revoked.
                grant.put("modelAllowed",false);out.put("privacy",grant);
            }
        }
        if(context.get("_historyRefs") instanceof List<?> refs) {
            List<Object> messages=new ArrayList<>();
            for(Object raw:refs) {
                var ref=db.object(raw);
                var rows=db.rows("SELECT m.content,g.result_json FROM chat_message m JOIN chat_generation g ON g.message_id=m.id WHERE m.id=? AND g.task_id=? AND m.user_id=? AND m.created_at>=? AND g.status='SUCCESS'",
                    ref.get("messageId"),ref.get("taskId"),context.get("userId"),cutoff());
                if(rows.isEmpty()) continue;
                messages.add(Map.of("role","user","content",excerpt(rows.get(0).get("content")),"scopes",ref.get("scopes")));
                messages.add(Map.of("role","assistant","content",excerpt(db.object(rows.get(0).get("result")).get("answer")),"scopes",ref.get("scopes")));
            }
            out.put("messages",messages);
        }
        return out;
    }

    private List<String> dataScopes(Map<String,Object> context,Map<String,Object> data) {
        Set<String> scopes=new TreeSet<>();
        Object read=data.get("scope");
        if(read instanceof List<?> list) for(Object key:list) if(AssistantPrivacyService.SCOPES.contains(key)) scopes.add(key.toString());
        if(context.get("document")!=null) scopes.add("document");
        if(context.get("_referenceScopes") instanceof List<?> derived) for(Object scope:derived)
            if(AssistantPrivacyService.SCOPES.contains(scope))scopes.add(scope.toString());
        if(!db.object(context.get("conditions")).isEmpty()) scopes.add("profile");
        if("SCHOOL_RECOMMEND".equals(db.object(context.get("preparedPlan")).get("action"))) scopes.add("profile");
        if(context.get("messages") instanceof List<?> messages) for(Object raw:messages) {
            Object used=db.object(raw).get("scopes");
            if(used instanceof List<?> list) for(Object scope:list) if(AssistantPrivacyService.SCOPES.contains(scope)) scopes.add(scope.toString());
        }
        if(context.get("_historyRefs") instanceof List<?> refs) for(Object raw:refs) {
            Object used=db.object(raw).get("scopes");
            if(used instanceof List<?> list) for(Object scope:list) if(AssistantPrivacyService.SCOPES.contains(scope)) scopes.add(scope.toString());
        }
        return new ArrayList<>(scopes);
    }

    private Map<String,Object> resolveTargets(Long owner,String conversationId,Map<String,Object> plan,Map<String,Object> page,String sourceTask,Map<String,Object> context) {
        if(plan.get("clarification")!=null) return page;
        String query=Objects.toString(plan.get("standaloneQuery"),"");
        String operation=Objects.toString(plan.get("operation"),"NONE");
        List<?> requested=plan.get("questionRefs") instanceof List<?> refs?refs:List.of();
        boolean related=query.matches("(?s).*(相关|同类|同知识点).*") &&
            ("PRACTICE_CREATE".equals(operation) || plan.get("reads") instanceof List<?> reads && reads.contains("documents"));
        if("NONE".equals(operation)&&requested.isEmpty()&&plan.get("ordinal")==null&&!related)return page;
        if(related&&page.get("documentId")!=null&&"NONE".equals(operation))return page;
        boolean earlier=query.matches("(?s).*(刚才|上一|上述|将其|把其|找到的|那道|该题).*");
        // A current collection request has its own scope; stale page selections and
        // historical aliases must not replace it. Explicit Q references still bind below.
        if(requested.isEmpty() && plan.get("ordinal")==null && !earlier &&
            Set.of("wrong","favorite").contains(Objects.toString(plan.get("target"))))
            return new LinkedHashMap<>(Map.of("page",plan.get("target")));
        // Explicit Q aliases always belong to a prior answer, never to a new read.
        if(requested.isEmpty() && sourceTask==null && !earlier && !related) {
            var explicit=java.util.regex.Pattern.compile("(?:平台题号|题目编号|题号|#)\\s*#?\\s*([1-9][0-9]{0,17})").matcher(query);
            if(explicit.find()) return selectedPage(page,List.of(Long.valueOf(explicit.group(1))),plan);
            if(plan.get("ordinal") instanceof Number ordinal) {
                List<?> shown=page.get("visibleQuestionIds") instanceof List<?> list?list:List.of();
                if(ordinal.intValue()<=shown.size()) return selectedPage(page,List.of(shown.get(ordinal.intValue()-1)),plan);
            } else if(page.get("selectedQuestionIds") instanceof List<?> selected && !selected.isEmpty()) return page;
            else if("NONE".equals(operation)||!"selected".equals(plan.get("target"))) return page;
        }
        var previous=sourceTask==null
            ? db.rows("SELECT context_json,result_json FROM chat_generation WHERE conversation_id=? AND user_id=? AND status='SUCCESS' AND created_at>=? ORDER BY created_at DESC,task_id DESC LIMIT 20",conversationId,owner,cutoff())
            : db.rows("SELECT context_json,result_json FROM chat_generation WHERE conversation_id=? AND user_id=? AND task_id=? AND status='SUCCESS' AND created_at>=?",conversationId,owner,sourceTask,cutoff());
        for(var row:previous) {
            var prior=db.object(row.get("context"));
            var data=db.object(prior.get("_learning"));
            var stored=db.object(data.get("_questionIds"));
            Map<String,Object> refs=new LinkedHashMap<>();
            if(db.object(row.get("result")).get("evidence") instanceof List<?> evidence) for(Object raw:evidence) {
                var e=db.object(raw);String ref=Objects.toString(e.get("ref"),"");
                var resource=db.object(e.get("resource"));
                if("question".equals(resource.get("type"))&&stored.containsKey(ref)&&Objects.equals(stored.get(ref),resource.get("id"))) refs.put(ref,stored.get(ref));
            }
            if(refs.isEmpty()) continue;
            context.put("_referenceScopes",db.object(row.get("result")).getOrDefault("dataScopes",List.of("wrong","favorite")));
            // Legacy answers exposed all candidates. Narrow them only by their
            // actual request and stored metadata, never by model prose.
            String priorQuery=Objects.toString(prior.get("userInput"),"");
            List<?> items=data.get("items") instanceof List<?> list?list:List.of();
            if(requested.isEmpty()) {
                Map<String,Object> focused=new LinkedHashMap<>();
                for(Object raw:items) {
                    var item=db.object(raw);String point=Objects.toString(item.get("knowledgePoint"),"");
                    String ref=Objects.toString(item.get("ref"),"");
                    if(!point.isBlank()&&priorQuery.contains(point)&&refs.containsKey(ref)) focused.put(ref,refs.get(ref));
                }
                if(!focused.isEmpty()) refs=focused;
            }
            List<Object> chosen=new ArrayList<>();
            if(!requested.isEmpty()) {
                for(Object ref:requested) { if(!refs.containsKey(ref)){chosen.clear();break;} chosen.add(refs.get(ref)); }
                // Do not skip an answer exposing Q1 to reinterpret Q1 in an older answer.
                if(chosen.isEmpty()) break;
            } else if(plan.get("ordinal") instanceof Number ordinal) {
                var shown=new ArrayList<>(refs.values());
                if(ordinal.intValue()>shown.size()) break;
                chosen.add(shown.get(ordinal.intValue()-1));
            } else chosen.addAll(refs.values());
            if(related) {
                Set<String> points=new LinkedHashSet<>(),subjects=new LinkedHashSet<>();
                for(Object raw:items) {
                    var item=db.object(raw);
                    if(!chosen.contains(stored.get(Objects.toString(item.get("ref"),""))))continue;
                    if(item.get("knowledgePoint") instanceof String p&&!p.isBlank())points.add(p);
                    if(item.get("subject") instanceof String s&&!s.isBlank())subjects.add(s);
                }
                if(plan.get("knowledgePoint")==null&&points.size()==1) plan.put("knowledgePoint",points.iterator().next());
                if(plan.get("subject")==null&&subjects.size()==1)plan.put("subject",subjects.iterator().next());
                if(plan.get("knowledgePoint")==null){clarifyTargets(plan,"相关题目涉及多个知识点，请明确想练习或查找资料的知识点。");return page;}
                if("normal".equals(plan.get("target")) || "NONE".equals(operation)) return page;
            }
            if(chosen.size()==1 || !requested.isEmpty() || "visible".equals(plan.get("target")))
                return selectedPage(db.object(prior.get("_pageContext")),chosen,plan);
            StringBuilder candidates=new StringBuilder("找到多道候选，请明确引用编号：");
            for(var ref:refs.entrySet()) {
                candidates.append(' ').append(ref.getKey());
                for(Object raw:items){var item=db.object(raw);if(ref.getKey().equals(item.get("ref")))candidates.append('（').append(Objects.toString(item.get("knowledgePoint"),"题目")).append('）');}
            }
            clarifyTargets(plan,candidates.toString());return page;
        }
        if(related&&plan.get("knowledgePoint")!=null)return page;
        clarifyTargets(plan,"请先选择要操作的题目，或引用助手回答中的Q编号；相关练习请明确知识点。");
        return page;
    }

    private Map<String,Object> selectedPage(Map<String,Object> page,List<?> ids,Map<String,Object> plan) {
        var selected=new LinkedHashMap<>(page);selected.put("selectedQuestionIds",ids);selected.put("visibleQuestionIds",ids);
        selected.putIfAbsent("page","practice");plan.put("questionRefs",List.of());plan.put("ordinal",null);plan.put("target","selected");
        return selected;
    }
    private void clarifyTargets(Map<String,Object> plan,String message) {
        String hint="\n推荐问法：将我的错题本中涉及 TCP 的题目加入收藏；若指上次回答，可说：收藏 Q1 和 Q2。";
        plan.put("operation","NONE");plan.put("clarification",(message.length()>750?message.substring(0,750)+"…":message)+hint);
    }

    private void checkAuthorization(Long owner,Map<String,Object> context,boolean checkProvider) {
        var consent=db.object(context.get("privacy"));
        int version=((Number)consent.getOrDefault("version",0)).intValue();
        privacy.check(owner,db.object(context.get("_grant")),version);
        if(checkProvider && Boolean.TRUE.equals(consent.get("modelAllowed")) && !privacy.provider().equals(context.get("_provider")))
            throw new ApiException(409,"模型接收端点已变化，请重新授权");
    }

    private void refreshActions(Long owner,Map<String,Object> attempt) {
        if(attempt.get("result") instanceof Map<?,?>) {
            var result=db.object(attempt.get("result"));
            result.put("actions",learning.actions(owner,Objects.toString(attempt.get("taskId"))));
            attempt.put("result",result);
        }
    }

    @EventListener public void privacyChanged(AssistantPrivacyService.Changed event) {
        stopOwner(event.owner(),null);
    }
    private void stopOwner(Long owner,String conversationId) {
        for(var row:db.rows("SELECT task_id FROM chat_generation WHERE user_id=? AND status='RUNNING'"+(conversationId==null?"":" AND conversation_id=?"),
                conversationId==null?new Object[]{owner}:new Object[]{owner,conversationId})) {
            var live=running.computeIfAbsent(row.get("taskId").toString(),Live::new);
            terminate(live,"CANCELLED","隐私设置变化或记录清除，生成已停止",null);
        }
    }

    public void clear(Long owner,String id) {
        if(id!=null) conversation(owner,id,false);
        stopOwner(owner,id);
        List<String> affected=new ArrayList<>();
        transactions.executeWithoutResult(tx -> {
            db.one("SELECT id FROM `user` WHERE id=? FOR UPDATE",owner);
            String suffix=id==null?"":" AND conversation_id=?";
            if(id==null) {
                var consent=db.rows("SELECT user_id FROM assistant_privacy WHERE user_id=?",owner);
                if(consent.isEmpty()) db.jdbc().update("INSERT INTO assistant_privacy(user_id,model_allowed,scopes_json,provider,version) VALUES(?,FALSE,'{}','',1)",owner);
                else db.jdbc().update("UPDATE assistant_privacy SET version=version+1,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",owner);
            }
            Object[] args=id==null?new Object[]{owner}:new Object[]{owner,id};
            for(var row:db.rows("SELECT task_id FROM chat_generation WHERE user_id=?"+suffix,args)) affected.add(row.get("taskId").toString());
            db.jdbc().update("UPDATE task SET status=CASE WHEN status='RUNNING' THEN 'CANCELLED' ELSE status END,input_payload=NULL,result_payload=NULL,release_id=NULL,error_message=NULL,deleted_at=CURRENT_TIMESTAMP WHERE user_id=?"+(id==null?"":" AND id IN (SELECT task_id FROM chat_generation WHERE user_id=?"+suffix+")"),
                id==null?new Object[]{owner}:new Object[]{owner,owner,id});
            db.jdbc().update("DELETE FROM assistant_action WHERE user_id=?"+suffix,args);
            db.jdbc().update("DELETE FROM chat_generation WHERE user_id=?"+suffix,args);
            db.jdbc().update("DELETE FROM chat_message WHERE user_id=?"+suffix,args);
            db.jdbc().update("DELETE FROM chat_conversation WHERE user_id=?"+(id==null?"":" AND id=?"),args);
        });
        for(String taskId:affected) {
            Live live=running.remove(taskId);
            if(live!=null) synchronized(live) { live.done=true;live.draft.clear();closeUpstream(live);live.listeners.forEach(SseEmitter::complete);live.listeners.clear(); }
        }
    }

    private java.time.LocalDateTime cutoff() { return java.time.LocalDateTime.now().minusDays(30); }
    public void cleanupExpired() {
        try {
            for(var row:db.rows("SELECT DISTINCT user_id FROM chat_message WHERE created_at<? UNION SELECT DISTINCT user_id FROM chat_generation WHERE created_at<?",cutoff(),cutoff())) cleanupOwner(((Number)row.get("userId")).longValue());
            // Empty conversations also have a private profile/title lifecycle.
            db.jdbc().update("DELETE FROM chat_conversation WHERE created_at<? AND id NOT IN (SELECT conversation_id FROM chat_message)",cutoff());
            db.jdbc().update("UPDATE task SET input_payload=NULL,result_payload=NULL,release_id=NULL,error_message=NULL,deleted_at=COALESCE(deleted_at,CURRENT_TIMESTAMP) WHERE created_at<?",cutoff());
        }
        catch(Exception e) { log.warn("assistantCleanupFailure={}",e.getClass().getSimpleName()); }
    }
    public void cleanupOwner(Long owner) {
        db.jdbc().update("UPDATE task SET input_payload=NULL,result_payload=NULL,release_id=NULL,error_message=NULL,deleted_at=COALESCE(deleted_at,CURRENT_TIMESTAMP) WHERE user_id=? AND created_at<?",owner,cutoff());
        var expired=db.rows("SELECT task_id FROM chat_generation WHERE user_id=? AND (created_at<? OR message_id IN (SELECT id FROM chat_message WHERE user_id=? AND created_at<?))",owner,cutoff(),owner,cutoff());
        if(expired.isEmpty()) return;
        for(var item:expired) {
            var live=running.get(item.get("taskId").toString());
            if(live!=null) terminate(live,"CANCELLED","记录已过期",null);
        }
        transactions.executeWithoutResult(tx -> {
            db.one("SELECT id FROM `user` WHERE id=? FOR UPDATE",owner);
            for(var item:expired) {
                String taskId=item.get("taskId").toString();
                db.jdbc().update("UPDATE task SET input_payload=NULL,result_payload=NULL,release_id=NULL,error_message=NULL,deleted_at=CURRENT_TIMESTAMP WHERE user_id=? AND id=?",owner,taskId);
                db.jdbc().update("DELETE FROM assistant_action WHERE user_id=? AND task_id=?",owner,taskId);
                db.jdbc().update("DELETE FROM chat_generation WHERE user_id=? AND task_id=?",owner,taskId);
            }
            db.jdbc().update("DELETE FROM chat_message WHERE user_id=? AND created_at<?",owner,cutoff());
            db.jdbc().update("DELETE FROM chat_conversation WHERE user_id=? AND id NOT IN (SELECT conversation_id FROM chat_message WHERE user_id=?) AND created_at<?",owner,owner,cutoff());
            db.jdbc().update("UPDATE chat_conversation SET title='学习会话',profile_json='{}',conditions_json='{}' WHERE user_id=? AND created_at<?",owner,cutoff());
        });
    }

    public Map<String,Object> confirm(Long owner,String id,String actionId) {
        cleanupOwner(owner); conversation(owner,id,false);
        var grant=com.kaoyan.security.UserContext.sessionGrant();
        return transactions.execute(tx -> {
            db.one("SELECT id FROM `user` WHERE id=? FOR UPDATE",owner);
            var source=db.one("SELECT g.context_json FROM assistant_action a JOIN chat_generation g ON g.task_id=a.task_id AND g.user_id=a.user_id WHERE a.id=? AND a.user_id=? AND a.conversation_id=?",actionId,owner,id);
            int version=((Number)db.object(db.object(source.get("context")).get("privacy")).getOrDefault("version",0)).intValue();
            privacy.check(owner,grant,version);
            return learning.confirm(owner,id,actionId);
        });
    }
    public Map<String,Object> dismiss(Long owner,String id,String actionId) {
        cleanupOwner(owner); conversation(owner,id,false);
        return learning.dismiss(owner,id,actionId);
    }
}
