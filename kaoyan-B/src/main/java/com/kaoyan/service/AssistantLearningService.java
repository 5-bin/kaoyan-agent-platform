package com.kaoyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.common.ApiException;
import com.kaoyan.dto.response.QuestionContentVO;
import com.kaoyan.entity.*;
import com.kaoyan.mapper.*;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;

/** Java-owned learning reads and fixed business commands. Internal underscore fields must never leave Java. */
@Service
@RequiredArgsConstructor
public class AssistantLearningService {
    private final PracticeRecordMapper attempts;
    private final QuestionMapper questions;
    private final DocumentMapper documents;
    private final UserQuestionMarkService marks;
    private final PracticeService practice;
    private final StudyStatService statistics;
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;
    private final QuestionSearchService questionSearch;

    public Map<String,Object> read(Long owner, Map<String,Object> plan, Map<String,Object> pageContext) {
        Map<String,Object> inputPage = pageContext == null ? Map.of() : pageContext;
        Set<String> reads = strings(plan.get("reads"));
        if (!Set.of("wrong","favorite","stats","practice","documents","questions").containsAll(reads)) throw bad("读取工具无效");
        String operation = string(plan,"operation","NONE");
        String target = string(plan,"target", "selected");
        boolean publicQuestions=reads.contains("questions") && "normal".equals(target);
        boolean collection=Set.of("wrong","favorite").contains(target);
        Map<String,Object> page=publicQuestions?Map.of():collection?Map.of("page",target):inputPage;
        String subject = string(plan,"subject",string(page,"subject",null));
        String knowledgePoint = string(plan,"knowledgePoint",null);
        boolean readQuestions=!"NONE".equals(operation)||reads.stream().anyMatch(Set.of("wrong","favorite","practice","questions")::contains);
        List<Long> visible = readQuestions?ids(page.get("visibleQuestionIds")):List.of();
        List<Long> selected = readQuestions?ids(page.get("selectedQuestionIds")):List.of();
        List<Long> concrete = new ArrayList<>();
        if(readQuestions && plan.get("ordinal") instanceof Number n) {
            int index=n.intValue()-1;if(index<0||index>=visible.size())throw bad("请明确所操作的题目");
            concrete.add(visible.get(index));
        } else if("selected".equals(target)) concrete.addAll(selected);
        boolean focused=!concrete.isEmpty();
        List<Long> ids = new ArrayList<>();
        if(focused) ids.addAll(concrete);
        else {
            // Keep the displayed order first; remaining rows still contribute the truthful total.
            if(!collection) ids.addAll(visible);
            if (collection?"wrong".equals(target):reads.contains("wrong")) marks.listWrong(owner).forEach(m -> ids.add(m.getQuestionId()));
            if (collection?"favorite".equals(target):reads.contains("favorite")) marks.listFavorite(owner).forEach(m -> ids.add(m.getQuestionId()));
            if (!collection && reads.contains("practice")) {
                String session = string(page,"sessionId",null);
                if (session != null) practice.sessionDetail(owner,session).forEach(r -> ids.add(r.getQuestionId()));
                else practice.lambdaQuery().eq(PracticeRecord::getUserId,owner).orderByDesc(PracticeRecord::getCreatedAt).list().forEach(r -> ids.add(r.getQuestionId()));
            }
            if (publicQuestions || "PRACTICE_CREATE".equals(operation) && "normal".equals(target))
                questionSearch.published().forEach(q -> ids.add(q.getId()));
        }
        // Page state contains only references. Load contents and validate membership again.
        for(Long id:focused?concrete:union(selected,visible))checkPageMembership(owner,page,id);
        Map<Long,Map<String,Object>> questionCandidates=new LinkedHashMap<>();
        Map<Long,QuestionContentVO> candidateViews=new LinkedHashMap<>();
        Map<Long,PracticeRecord> candidateRecords=new LinkedHashMap<>();
        Map<String,Object> candidateFingerprints=new LinkedHashMap<>();
        int missingSnapshots=0;
        for(Long id:ids.stream().distinct().toList()) {
            // Capture before loading contents; a concurrent edit invalidates the preview.
            Map<String,Object> originalFingerprint=fingerprint(owner,id);
            Question current=questions.selectById(id);
            PracticeRecord record=publicQuestions?null:contextRecord(owner,page,id);
            if(!QuestionHistoryView.playable(current)&&(record==null||record.getIsCorrect()==null))continue;
            QuestionContentVO view=new QuestionContentVO();QuestionHistoryView.populate(view,record,current);
            if(view.getContent()==null){missingSnapshots++;continue;}
            if(subject!=null&&!subject.equals(view.getSubject()))continue;
            if(plan.get("difficulty")!=null&&!plan.get("difficulty").equals(view.getDifficulty()))continue;
            Map<String,Object> snapshot=new LinkedHashMap<>();snapshot.put("id",id);snapshot.put("version",view.getVersion());
            Map<String,Object> fields=json.convertValue(view,new TypeReference<LinkedHashMap<String,Object>>(){});
            for(String key:List.of("subject","difficulty","knowledgePoint","content","optionA","optionB","optionC","optionD")) {
                snapshot.put(key,Objects.toString(fields.get(key),""));
            }
            questionCandidates.put(id,snapshot);
            candidateViews.put(id,view);candidateRecords.put(id,record);candidateFingerprints.put(id.toString(),originalFingerprint);
        }
        Map<String,Object> result = new LinkedHashMap<>();
        Map<Long,Map<String,Object>> matchInfo=new LinkedHashMap<>();
        List<Long> filtered=new ArrayList<>(questionCandidates.keySet());
        if(knowledgePoint!=null) {
            var search=questionSearch.search(knowledgePoint,new ArrayList<>(questionCandidates.values()));
            String state=search==null?"UNAVAILABLE":search.status();
            result.put("retrievalStatus",state);result.put("matchTopic",knowledgePoint);
            if(search!=null)result.put("_questionRelease",search.releaseId());
            filtered=new ArrayList<>();
            if("READY".equals(state)) {
                for(var match:search.matches()) {
                    Long id=((Number)match.get("id")).longValue();
                    if(!questionCandidates.containsKey(id))throw bad("题目匹配结果无效");
                    filtered.add(id);matchInfo.put(id,match);
                }
            } else result.put("notice",switch(state) {
                case "BUILDING","BUSY" -> "已识别主题“"+knowledgePoint+"”，题目语义索引正在准备，请稍后重试；本次未修改记录。";
                case "FAILED" -> "已识别主题“"+knowledgePoint+"”，题目索引构建失败，请检查本地模型与索引配置；本次未修改记录。";
                default -> "已识别主题“"+knowledgePoint+"”，题目检索服务暂时不可用，请稍后重试；本次未修改记录。";
            });
            result.put("_topicMatches",matchInfo);
            Map<String,Object> titles=new LinkedHashMap<>();
            for(Long id:filtered)titles.put(id.toString(),questionCandidates.get(id).get("content"));
            result.put("_matchedTitles",titles);
            Map<String,Object> fingerprints=new LinkedHashMap<>();
            for(Long id:filtered)fingerprints.put(id.toString(),candidateFingerprints.get(id.toString()));
            result.put("_matchFingerprints",fingerprints);
        }
        if(missingSnapshots>0)result.put("notice",Objects.toString(result.get("notice"),"")+" 有"+missingSnapshots+"道历史题目快照缺失，未按现行题目补造匹配依据。");
        List<Map<String,Object>> items = new ArrayList<>(), evidence = new ArrayList<>();
        Map<String,Long> refs = new LinkedHashMap<>();
        for (Long id : filtered.stream().limit(20).toList()) {
            PracticeRecord r = candidateRecords.get(id); QuestionContentVO view = candidateViews.get(id);
            boolean answered=r!=null&&r.getIsCorrect()!=null;
            Map<String,Object> item = json.convertValue(view,new TypeReference<LinkedHashMap<String,Object>>(){});
            String ref = "Q"+(items.size()+1); item.put("ref",ref);
            item.put("answered",answered);item.put("snapshotMissing","MISSING".equals(view.getSnapshotStatus())||"UNAVAILABLE".equals(view.getSnapshotStatus()));
            item.put("scope",publicQuestions?"questions":"wrong".equals(target)?"wrong":marks.isFavorite(owner,id)&&(reads.contains("favorite")||"favorite".equals(page.get("page")))?"favorite":"wrong");
            if(!publicQuestions)item.put("inWrongBook",marks.listWrong(owner).stream().anyMatch(mark -> id.equals(mark.getQuestionId())));
            if(matchInfo.containsKey(id)) {item.put("matchMethod",matchInfo.get(id).get("method"));item.put("matchTopic",knowledgePoint);}
            if (r != null) {item.put("userAnswer",r.getUserAnswer());item.put("correct",r.getIsCorrect());}
            items.add(item); refs.put(ref,id);
            Map<String,Object> e = new LinkedHashMap<>(); e.put("ref",ref);e.put("kind",answered ? "attempt" : "question");
            e.put("title",view.getKnowledgePoint()==null ? "题目" : view.getKnowledgePoint());
            e.put("locator",!answered ? "尚未作答；不含标准答案" : switch(Objects.toString(view.getSnapshotStatus(),"MISSING")) {
                case "AVAILABLE" -> "本人已判分的题目版本";
                case "PARTIAL" -> "本人已判分版本；旧快照部分字段缺失";
                case "UNAVAILABLE" -> "本人历史作答；题目当前不可用";
                default -> "本人作答的题目版本快照缺失";
            });
            if(matchInfo.containsKey(id)){e.put("matchMethod",matchInfo.get(id).get("method"));e.put("matchTopic",knowledgePoint);e.put("summary",Objects.toString(view.getContent(),"").substring(0,Math.min(180,Objects.toString(view.getContent(),"").length())));}
            e.put("version",view.getVersion());e.put("resource",Map.of("type","question","id",id));evidence.add(e);
        }
        result.put("items",items);result.put("total",filtered.size());result.put("readCount",items.size());
        result.put("_questionIds",refs);
        result.put("_operationQuestionIds",filtered.stream().limit(50).toList());
        List<String> scopes = new ArrayList<>();
        for (String scope : List.of("wrong","favorite","stats")) if(reads.contains(scope)) scopes.add(scope);
        if (reads.contains("practice") && !scopes.contains("wrong")) scopes.add("wrong");
        for(Map<String,Object> item:items) {String category=item.get("scope").toString();if(!scopes.contains(category))scopes.add(category);}
        result.put("scope",scopes);
        if (reads.contains("stats")) {
            Map<String,Object> stats = statistics.learning(owner,date(plan,page,"from"),date(plan,page,"to"),subject);
            result.put("statistics",stats);evidence.add(Map.of("ref","S1","kind","stats","title","有效作答统计","locator",stats.get("from")+"至"+stats.get("to"),"version","computed","resource",Map.of("type","stats","id","learning")));
        }
        if (reads.contains("documents")) {
            var query = new LambdaQueryWrapper<Document>().eq(Document::getStatus,"PUBLISHED").eq(subject!=null&&!subject.isBlank(),Document::getSubject,subject);
            Long documentId = number(page.get("documentId"));
            if (documentId!=null) query.eq(Document::getId,documentId);
            List<Map<String,Object>> found = new ArrayList<>();
            List<Document> candidates=documents.selectList(query.orderByDesc(Document::getUpdatedAt));
            if(documentId!=null&&candidates.isEmpty())throw missing();
            String queryText=string(plan,"standaloneQuery","");
            if(documentId==null) candidates=candidates.stream().sorted(Comparator.comparingInt((Document d)->relevance(d,queryText)).reversed())
                    .filter(d->knowledgePoint!=null ? (Objects.toString(d.getTitle(),"")+Objects.toString(d.getContent(),"")).contains(knowledgePoint)
                        : (subject!=null&&!subject.isBlank())||relevance(d,queryText)>0).limit(5).toList();
            for (Document d : candidates) {
                String content = d.getContent()==null ? "" : d.getContent(); String ref="D"+(found.size()+1);
                Map<String,Object> doc = new LinkedHashMap<>();doc.put("ref",ref);doc.put("title",d.getTitle());
                doc.put("content",content.substring(0,Math.min(content.length(),12000)));doc.put("excerpt",true);doc.put("truncated",content.length()>12000);doc.put("locator","正文字符1—"+Math.min(content.length(),12000));doc.put("source","已发布资料；原文页码未记录");
                doc.put("sourceUrl",safeUrl(d.getSourceUrl()));doc.put("version",hash(content));found.add(doc);
                Map<String,Object> e = new LinkedHashMap<>();e.put("ref",ref);e.put("kind","published_document");e.put("title",d.getTitle());
                e.put("locator","正文字符1—"+Math.min(content.length(),12000)+"；原文页码与正式版本未记录");e.put("version",hash(content));
                e.put("resource",Map.of("type","document","id",d.getId()));e.put("sourceUrl",safeUrl(d.getSourceUrl()));evidence.add(e);
            }
            result.put("documents",found);
        }
        result.put("evidence",evidence);return result;
    }

    @Transactional
    public List<Map<String,Object>> finalizeActions(Long owner,String conversationId,String taskId,Map<String,Object> plan,Map<String,Object> pageContext,Map<String,Object> learningContext) {
        String operation = string(plan,"operation","NONE");
        if ("NONE".equals(operation)) return List.of();
        if (!Set.of("FAVORITE_ADD","FAVORITE_REMOVE","WRONG_REMOVE","PRACTICE_CREATE").contains(operation)) throw bad("操作类型无效");
        List<Map<String,Object>> previous=actions(owner,taskId);if(!previous.isEmpty())return previous;
        Map<String,Object> page=pageContext==null?Map.of():pageContext;
        Map<String,Object> context=learningContext==null?Map.of():learningContext;
        String target=string(plan,"target","selected");
        List<Long> targets=new ArrayList<>();
        if ("wrong".equals(target)) marks.listWrong(owner).forEach(m->targets.add(m.getQuestionId()));
        else if ("favorite".equals(target)) marks.listFavorite(owner).forEach(m->targets.add(m.getQuestionId()));
        else if ("visible".equals(target)) targets.addAll(ids(page.get("visibleQuestionIds")));
        else if ("selected".equals(target)) targets.addAll(ids(page.get("selectedQuestionIds")));
        else if (!"normal".equals(target)) throw bad("操作目标无效");
        if (context.containsKey("_operationQuestionIds") && Set.of("wrong","favorite","normal").contains(target)) {
            targets.clear(); targets.addAll(ids(context.get("_operationQuestionIds")));
        }
        Object ordinal=plan.get("ordinal");
        if(ordinal instanceof Number n) {
            List<Long> shown=ids(page.get("visibleQuestionIds"));int index=n.intValue()-1;
            if(index<0||index>=shown.size())throw bad("请明确所操作的题目");targets.clear();targets.add(shown.get(index));
        }
        Set<String> requested=strings(plan.get("questionRefs"));
        if(!requested.isEmpty()) {
            targets.clear();Object stored=context.get("_questionIds");
            if(!(stored instanceof Map<?,?> refs))throw bad("题目引用失效，请重新选择");
            for(String ref:requested){Long id=number(refs.get(ref));if(id==null)throw bad("题目引用无效");targets.add(id);}
        }
        targets.replaceAll(id->{checkPageMembership(owner,page,id);return id;});
        List<Long> unique=targets.stream().distinct().toList();
        String subject=string(plan,"subject",string(page,"subject",null));
        String difficulty=string(plan,"difficulty",null);
        String knowledgePoint=string(plan,"knowledgePoint",null);
        boolean topicMatched=knowledgePoint!=null && "READY".equals(context.get("retrievalStatus")) && context.get("_topicMatches") instanceof Map<?,?>;
        if(knowledgePoint!=null&&context.get("retrievalStatus")!=null&&!topicMatched)return List.of();
        if(topicMatched) {
            Map<?,?> matched=(Map<?,?>)context.get("_topicMatches");
            Map<?,?> fixed=(Map<?,?>)context.get("_matchFingerprints");
            unique=unique.stream().filter(qid->matched.containsKey(qid)||matched.containsKey(qid.toString()))
                .filter(qid->QuestionHistoryView.playable(questions.selectById(qid))).toList();
            for(Long qid:unique)if(fixed==null||!Objects.equals(encode(fixed.get(qid.toString())),encode(fingerprint(owner,qid))))
                throw new ApiException(409,409,"目标已变化，请重新生成操作预览");
        }
        if(subject!=null&&!topicMatched)unique=unique.stream().filter(id->{Question q=questions.selectById(id);return q!=null&&subject.equals(q.getSubject());}).toList();
        if(knowledgePoint!=null&&!topicMatched)unique=unique.stream().filter(id->{Question q=questions.selectById(id);return q!=null&&LearningTopic.matches(knowledgePoint,q.getKnowledgePoint());}).toList();
        int count=plan.get("count") instanceof Number n?n.intValue():5;
        if(count<1||count>50)throw bad("题目数量须为1至50");
        if ("PRACTICE_CREATE".equals(operation)) {
            if(topicMatched) {
                Map<?,?> matched=(Map<?,?>)context.get("_topicMatches");
                unique=unique.stream().filter(qid->{Object rawMatch=matched.containsKey(qid)?matched.get(qid):matched.get(qid.toString());
                    Question current=questions.selectById(qid);
                    return rawMatch instanceof Map<?,?> match && current!=null && Objects.equals(match.get("version"),current.getVersion());}).toList();
            }
            if("normal".equals(target)&&unique.isEmpty()&&!context.containsKey("_operationQuestionIds"))
                unique=questions.selectForPractice(subject,difficulty,knowledgePoint,count).stream().map(Question::getId)
                    .filter(qid->LearningTopic.matches(knowledgePoint,questions.selectById(qid).getKnowledgePoint())).toList();
            unique=unique.stream().filter(id->{Question q=questions.selectById(id);return QuestionHistoryView.playable(q)&&(difficulty==null||difficulty.equals(q.getDifficulty()));}).limit(count).toList();
        }
        if(unique.isEmpty())return List.of();
        if(unique.size()>50)throw bad("单次最多操作50题，请缩小范围");
        List<Map<String,Object>> snapshots=new ArrayList<>();
        for(Long id:unique){ensureAccessible(owner,id);snapshots.add(fingerprint(owner,id));}
        Map<String,Object> payload=new LinkedHashMap<>();payload.put("questionIds",unique);payload.put("snapshots",snapshots);
        payload.put("targets",unique.stream().map(qid -> {
            Question q=questions.selectById(qid);
            String title=q==null||q.getContent()==null?"历史题目":q.getContent();
            if(topicMatched&&context.get("_matchedTitles") instanceof Map<?,?> titles)title=Objects.toString(titles.get(qid.toString()),title);
            Map<String,Object> display=new LinkedHashMap<>();display.put("title",title.substring(0,Math.min(120,title.length())));display.put("resource",Map.of("type","question","id",qid));
            if(topicMatched){Map<?,?> matched=(Map<?,?>)context.get("_topicMatches");Object info=matched.containsKey(qid)?matched.get(qid):matched.get(qid.toString());
                if(info instanceof Map<?,?> m){display.put("matchMethod",m.get("method"));display.put("matchTopic",knowledgePoint);}}
            return display;
        }).toList());
        payload.put("source", "wrong".equals(target)?"WRONG":"favorite".equals(target)?"FAVORITE":"NORMAL");
        payload.put("subject",subject);payload.put("difficulty",difficulty);payload.put("count",count);
        String id=UUID.randomUUID().toString();
        boolean direct=knowledgePoint==null&&"FAVORITE_ADD".equals(operation)&&unique.size()==1&&(!requested.isEmpty()||ordinal!=null||"selected".equals(target));
        jdbc.update("INSERT INTO assistant_action(id,user_id,conversation_id,task_id,operation,status,payload_json,result_json,created_at,updated_at) VALUES (?,?,?,?,?,'PENDING',?,'{}',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",id,owner,conversationId,taskId,operation,encode(payload));
        if(direct)execute(id,owner,operation,payload);
        return actions(owner,taskId);
    }

    public List<Map<String,Object>> actions(Long owner,String taskId) {
        return jdbc.queryForList("SELECT * FROM assistant_action WHERE user_id=? AND task_id=? AND created_at>=?",owner,taskId,LocalDateTime.now().minusDays(30)).stream().map(this::view).toList();
    }
    @Transactional
    public Map<String,Object> confirm(Long owner,String conversationId,String actionId) {
        Map<String,Object> row=owned(owner,conversationId,actionId);
        if(!"PENDING".equals(row.get("status")))return view(row);
        Map<String,Object> payload=decode(row.get("payload_json"));
        execute(actionId,owner,String.valueOf(row.get("operation")),payload);
        return view(owned(owner,conversationId,actionId));
    }
    @Transactional
    public Map<String,Object> dismiss(Long owner,String conversationId,String actionId) {
        Map<String,Object> row=owned(owner,conversationId,actionId);
        if("PENDING".equals(row.get("status")))jdbc.update("UPDATE assistant_action SET status='DISMISSED',payload_json='{}',updated_at=CURRENT_TIMESTAMP WHERE id=?",actionId);
        return view(owned(owner,conversationId,actionId));
    }
    private Map<String,Object> owned(Long owner,String conversationId,String id) {
        var rows=jdbc.queryForList("SELECT a.* FROM assistant_action a JOIN chat_conversation c ON c.id=a.conversation_id AND c.user_id=a.user_id JOIN task t ON t.id=a.task_id AND t.user_id=a.user_id WHERE a.id=? AND a.user_id=? AND a.conversation_id=? AND t.status='SUCCESS' AND t.deleted_at IS NULL AND a.created_at>=? FOR UPDATE",id,owner,conversationId,LocalDateTime.now().minusDays(30));
        if(rows.isEmpty())throw missing();return rows.get(0);
    }
    private void execute(String id,Long owner,String operation,Map<String,Object> payload) {
        List<Long> targets=ids(payload.get("questionIds"));
        Object raw=payload.get("snapshots");if(!(raw instanceof List<?> snapshots)||snapshots.size()!=targets.size())throw bad("操作已失效");
        for(int i=0;i<targets.size();i++){
            questions.selectForUpdate(targets.get(i));ensureAccessible(owner,targets.get(i));
            if(!Objects.equals(encode(snapshots.get(i)),encode(fingerprint(owner,targets.get(i)))))throw new ApiException(409,409,"目标已变化，请重新生成操作预览");
        }
        Map<String,Object> result=new LinkedHashMap<>();
        if("PRACTICE_CREATE".equals(operation)){
            String session=practice.startSession(owner,string(payload,"subject",null),string(payload,"difficulty",null),targets.size(),string(payload,"source","NORMAL"),targets);
            result.put("sessionId",session);result.put("actualCount",practice.sessionDetail(owner,session).size());
        }else for(Long q:targets)switch(operation){case "FAVORITE_ADD"->marks.toggleFavorite(owner,q,true);case "FAVORITE_REMOVE"->marks.toggleFavorite(owner,q,false);case "WRONG_REMOVE"->marks.removeWrong(owner,q);default->throw bad("操作无效");}
        if(!result.containsKey("actualCount"))result.put("actualCount",targets.size());
        // Keep targets only until expiry so a repeated request returns the original outcome.
        jdbc.update("UPDATE assistant_action SET status='SUCCESS',result_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",encode(result),id,owner);
    }
    private Map<String,Object> fingerprint(Long owner,Long id) {
        Question q=questions.selectById(id);Map<String,Object> result=new LinkedHashMap<>();result.put("id",id);
        result.put("version",q==null?null:q.getVersion());result.put("active",q==null?null:q.getActive());result.put("review",q==null?null:q.getReviewStatus());
        UserQuestionMark mark=marks.lambdaQuery().eq(UserQuestionMark::getUserId,owner).eq(UserQuestionMark::getQuestionId,id).one();
        result.put("favorite",mark==null?0:mark.getIsFavorite());result.put("wrong",mark==null?0:mark.getIsWrong());
        result.put("contentHash",q==null?null:hash(encode(QuestionSearchService.snapshot(q))));
        PracticeRecord record=latest(owner,id);result.put("historyHash",record==null?null:hash(encode(record.getQuestionSnapshot())));return result;
    }
    private Map<String,Object> view(Map<String,Object> row) {
        String operation=String.valueOf(row.get("operation"));Map<String,Object> payload=decode(row.get("payload_json"));
        Map<String,Object> result=new LinkedHashMap<>();result.put("id",row.get("id"));result.put("type",operation);result.put("status",row.get("status"));
        result.put("title",switch(operation){case "FAVORITE_ADD"->"收藏题目";case "FAVORITE_REMOVE"->"取消收藏";case "WRONG_REMOVE"->"移出错题";case "PRACTICE_CREATE"->"创建练习";default->"学习操作";});
        result.put("count",ids(payload.get("questionIds")).size());result.put("requiresConfirmation","PENDING".equals(row.get("status")));
        result.put("targets",payload.getOrDefault("targets",List.of()));
        if("PRACTICE_CREATE".equals(operation)) result.put("requestedCount",payload.getOrDefault("count",result.get("count")));
        result.put("result",decode(row.get("result_json")));return result;
    }
    private void checkPageMembership(Long owner,Map<String,Object> page,Long id){
        String source=string(page,"page","");
        if("wrong".equals(source)&&marks.listWrong(owner).stream().noneMatch(m->id.equals(m.getQuestionId())))throw missing();
        if("favorite".equals(source)&&!marks.isFavorite(owner,id))throw missing();
        String session=string(page,"sessionId",null);
        if("practice".equals(source)&&session!=null&&practice.sessionDetail(owner,session).stream().noneMatch(r->id.equals(r.getQuestionId())))throw missing();
        ensureAccessible(owner,id);
    }
    private void ensureAccessible(Long owner,Long id){
        if(!QuestionHistoryView.playable(questions.selectById(id))&&latest(owner,id)==null)throw missing();
    }
    private PracticeRecord contextRecord(Long owner,Map<String,Object> page,Long id) {
        String session=string(page,"sessionId",null);
        if("practice".equals(page.get("page"))&&session!=null)
            return practice.sessionDetail(owner,session).stream().filter(r->id.equals(r.getQuestionId())).findFirst().orElseThrow(AssistantLearningService::missing);
        return latest(owner,id);
    }
    private PracticeRecord latest(Long owner,Long id){return attempts.selectOne(new LambdaQueryWrapper<PracticeRecord>().eq(PracticeRecord::getUserId,owner).eq(PracticeRecord::getQuestionId,id).eq(PracticeRecord::getGradingStatus,"valid").isNotNull(PracticeRecord::getIsCorrect).orderByDesc(PracticeRecord::getAnsweredAt).orderByDesc(PracticeRecord::getId).last("LIMIT 1"));}
    private static List<Long> union(List<Long> a,List<Long>b){List<Long> r=new ArrayList<>(a);r.addAll(b);return r;}
    private static List<Long> ids(Object value){if(value==null)return List.of();if(!(value instanceof List<?> list)||list.size()>50)throw bad("题目集合无效");List<Long> result=new ArrayList<>();for(Object item:list){Long id=number(item);if(id==null||id<1)throw bad("题目编号无效");result.add(id);}return result;}
    private static Long number(Object value){if(value instanceof Number n)return n.longValue();if(value instanceof String s&&s.matches("[1-9][0-9]{0,17}"))return Long.valueOf(s);return null;}
    private static Set<String> strings(Object value){if(value==null)return Set.of();if(!(value instanceof Collection<?> c)||c.size()>50)throw bad("参数集合无效");Set<String> values=new LinkedHashSet<>();for(Object item:c){if(!(item instanceof String s))throw bad("参数无效");values.add(s);}return values;}
    private static String string(Map<String,Object> map,String key,String fallback){return map.get(key) instanceof String s&&!s.isBlank()?s:fallback;}
    private static LocalDate date(Map<String,Object> plan,Map<String,Object> page,String key){String value=string(plan,key,string(page,key,null));try{return value==null?null:LocalDate.parse(value);}catch(Exception e){throw bad("日期无效");}}
    private static String safeUrl(String value){if(value==null)return null;try{var uri=java.net.URI.create(value);return "https".equals(uri.getScheme())&&uri.getHost()!=null&&uri.getUserInfo()==null?value:null;}catch(Exception e){return null;}}
    private static int relevance(Document d,String query) {
        String searchable=Objects.toString(d.getTitle(),"")+" "+Objects.toString(d.getSubject(),"")+" "+Objects.toString(d.getContent(),"");
        String clean=query.replaceAll("[\\p{Punct}\\s]", "");
        int score=0;for(int i=0;i+1<Math.min(clean.length(),200);i++)if(searchable.contains(clean.substring(i,i+2)))score++;
        if(d.getTitle()!=null&&query.contains(d.getTitle()))score+=20;return score;
    }
    private static String hash(String text){try{return java.util.HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)));}catch(Exception e){throw new IllegalStateException(e);}}
    private String encode(Object value){try{return json.writeValueAsString(value);}catch(Exception e){throw new IllegalStateException("操作序列化失败");}}
    private Map<String,Object> decode(Object value){if(value==null)return Map.of();try{return json.readValue(String.valueOf(value),new TypeReference<LinkedHashMap<String,Object>>(){});}catch(Exception e){throw new IllegalStateException("操作记录不可读取");}}
    private static ApiException bad(String message){return new ApiException(400,400,message);}
    private static ApiException missing(){return new ApiException(404,404,"资源不存在");}
}
