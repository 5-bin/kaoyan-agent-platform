package com.kaoyan;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.common.ApiException;
import com.kaoyan.entity.*;
import com.kaoyan.mapper.*;
import com.kaoyan.service.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import com.kaoyan.feign.AgentFeignClient;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(properties={
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.url=jdbc:h2:mem:assistant-learning;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER",
    "spring.datasource.username=sa", "spring.datasource.password=",
    "spring.sql.init.mode=always", "spring.sql.init.schema-locations=classpath:schema-test.sql,classpath:schema-practice.sql",
    "jwt.secret=test-only-jwt-key-at-least-32-characters",
    "kaoyan.agent.internal-key=test-only-internal-key-12345", "oss.endpoint=", "oss.access-key-id="
})
class AssistantLearningServiceTest {
    @Autowired AssistantLearningService assistant;
    @Autowired PracticeService practice;
    @Autowired StudyStatService stats;
    @Autowired UserQuestionMarkService marks;
    @Autowired QuestionMapper questions;
    @Autowired PracticeRecordMapper records;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper json;
    @MockitoBean AgentFeignClient agent;
    @MockitoBean QuestionSearchService search;
    @BeforeEach void deterministicSearchContract() {
        when(search.published()).thenAnswer(call->questions.selectList(new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<Question>()
            .eq(Question::getActive,1).eq(Question::getReviewStatus,"APPROVED").orderByAsc(Question::getId)));
        when(search.search(anyString(),anyList())).thenAnswer(call->{
            String topic=call.<String>getArgument(0).replace("传输控制协议","TCP").replace("TCP协议","TCP");List<Map<String,Object>> candidates=call.getArgument(1);
            var matches=candidates.stream().filter(row->java.util.regex.Pattern.compile("(?<![A-Z0-9])"+java.util.regex.Pattern.quote(topic.toUpperCase())+"(?![A-Z0-9])").matcher(Objects.toString(row.get("knowledgePoint"),"").toUpperCase()).find())
                .map(row->{Map<String,Object> m=new LinkedHashMap<>();m.put("id",row.get("id"));m.put("version",row.get("version"));m.put("method","LABEL");return m;}).toList();
            return new QuestionSearchService.Result("READY","synthetic-index",matches);
        });
    }
    @MockitoBean StringRedisTemplate redis;

    Question question() {
        Question q=new Question();q.setSubject("synthetic-"+UUID.randomUUID());q.setKnowledgePoint("进程调度");
        q.setContent("合成题干");q.setOptionA("甲");q.setOptionB("乙");q.setOptionC("丙");q.setOptionD("丁");
        q.setAnswer("B");q.setAnalysis("合成解析");q.setVersion(1);q.setActive(1);q.setReviewStatus("APPROVED");
        q.setQuestionType("SINGLE_CHOICE");q.setDifficulty("EASY");q.setStableOrder(1);questions.insert(q);return q;
    }
    long owner(){return Math.abs(UUID.randomUUID().getMostSignificantBits()%1000000000)+1000;}
    String conversation(long owner){String id=UUID.randomUUID().toString();jdbc.update("INSERT INTO chat_conversation(id,user_id,title,conditions_json,profile_json) VALUES(?,?,'synthetic','{}','{}')",id,owner);return id;}
    String task(long owner){String id=UUID.randomUUID().toString();jdbc.update("INSERT INTO task(id,user_id,task_type,status,created_at) VALUES(?,?,'CHAT','SUCCESS',CURRENT_TIMESTAMP)",id,owner);return id;}
    Map<String,Object> page(Question q){return Map.of("page","practice","selectedQuestionIds",List.of(q.getId()),"visibleQuestionIds",List.of(q.getId()));}
    @SuppressWarnings("unchecked") Map<String,Object> item(Map<String,Object> read){return ((List<Map<String,Object>>)read.get("items")).get(0);}

    @Test void creationSnapshotRemainsFixedAndUnansweredAnswersNeverEscape() {
        long owner=owner();Question q=question();String s=practice.startSession(owner,q.getSubject(),null,1);
        var pendingPage=practice.pageSessions(owner,1,20);
        assertEquals(1,pendingPage.getTotal(),"新建未答批次也必须可见");
        assertEquals(s,pendingPage.getList().get(0).getSessionId());assertEquals(0,pendingPage.getList().get(0).getAnswered());
        q.setAnswer("A");q.setContent("现行新题");q.setOptionB(null);q.setVersion(2);jdbc.update("UPDATE question SET answer='A',content='现行新题',option_b=NULL,version=2 WHERE id=?",q.getId());
        var before=practice.pageReview(owner,s,1,20).getList().get(0);
        assertEquals("合成题干",before.getContent());assertEquals("乙",before.getOptionB());assertNull(before.getAnswer());
        assertEquals(1,practice.answer(owner,s,q.getId(),"B").isCorrect());
        var after=practice.pageReview(owner,s,1,20).getList().get(0);assertEquals("B",after.getAnswer());assertEquals(1,after.getVersion());
        marks.toggleFavorite(owner,q.getId(),true);
        var read=assistant.read(owner,Map.of("reads",List.of("favorite")),Map.of());
        assertEquals(true,item(read).get("answered"));assertEquals("B",item(read).get("answer"));assertFalse(item(read).containsKey("id"));
        long other=owner();marks.toggleFavorite(other,q.getId(),true);
        var hidden=assistant.read(other,Map.of("reads",List.of("favorite")),Map.of());
        assertEquals(false,item(hidden).get("answered"));assertFalse(item(hidden).containsKey("answer"));
        q.setActive(0);questions.updateById(q);
        assertThrows(ApiException.class,()->practice.startSession(owner,null,null,1,"FAVORITE",List.of(q.getId())));
    }

    @Test void topicFilteringPrecedesExcerptLimitAndWrongMembershipDoesNotMeanLatestAnswerWrong() {
        long owner=owner();Question heap=question();heap.setKnowledgePoint("堆");questions.updateById(heap);marks.markWrong(owner,heap.getId());
        jdbc.update("UPDATE user_question_mark SET last_wrong_at=? WHERE user_id=? AND question_id=?",LocalDateTime.now().minusDays(5),owner,heap.getId());
        for(int i=0;i<24;i++) {Question other=question();other.setSubject(heap.getSubject());other.setKnowledgePoint("队列");questions.updateById(other);marks.markWrong(owner,other.getId());}
        var plan=Map.<String,Object>of("reads",List.of("wrong"),"subject",heap.getSubject(),"knowledgePoint","堆");
        var read=assistant.read(owner,plan,Map.of());
        assertEquals(1,read.get("total"));assertEquals(Map.of("Q1",heap.getId()),read.get("_questionIds"));
        assertFalse(item(read).containsKey("answer"));
        String session=practice.startSession(owner,heap.getSubject(),null,1,"WRONG",List.of(heap.getId()));
        practice.answer(owner,session,heap.getId(),"B");
        read=assistant.read(owner,plan,Map.of());
        assertEquals(true,item(read).get("inWrongBook"));assertEquals(1,item(read).get("correct"));
    }

    @Test void relatedPracticeIsFilteredAndDoesNotSubstituteUnrelatedQuestionsWhenScarce() {
        long owner=owner();Question heap=question();heap.setKnowledgePoint("堆");questions.updateById(heap);
        Question other=question();other.setSubject(heap.getSubject());other.setKnowledgePoint("队列");questions.updateById(other);
        var plan=Map.<String,Object>of("reads",List.of(),"operation","PRACTICE_CREATE","target","normal","subject",heap.getSubject(),"knowledgePoint","堆","count",5);
        var data=assistant.read(owner,plan,Map.of());String conversation=conversation(owner);
        var action=assistant.finalizeActions(owner,conversation,task(owner),plan,Map.of(),data).get(0);
        assertEquals(1,action.get("count"));assertEquals(5,action.get("requestedCount"));assertEquals("PENDING",action.get("status"));
        var confirmed=assistant.confirm(owner,conversation,action.get("id").toString());
        var result=json.convertValue(confirmed.get("result"),Map.class);
        var rows=practice.sessionDetail(owner,result.get("sessionId").toString());
        assertEquals(List.of(heap.getId()),rows.stream().map(PracticeRecord::getQuestionId).toList());
        var missing=new LinkedHashMap<>(plan);missing.put("knowledgePoint","不存在的专题");
        assertTrue(assistant.finalizeActions(owner,conversation,task(owner),missing,Map.of(),assistant.read(owner,missing,Map.of())).isEmpty());
    }

    @Test void collectionTopicReadsAndPreviewExcludeOtherCollectionsAndPageSelections() {
        long owner=owner();Question first=question(),second=question(),favoriteOnly=question(),foreign=question(),noise=question();
        for(Question q:List.of(first,second,favoriteOnly,foreign,noise)) {
            q.setSubject(first.getSubject());q.setKnowledgePoint(q==noise?"ATCP":q==second?"TCP序号":"TCP拥塞控制");questions.updateById(q);
        }
        for(Question q:List.of(first,second,noise))marks.markWrong(owner,q.getId());
        marks.toggleFavorite(owner,favoriteOnly.getId(),true);marks.markWrong(owner+1,foreign.getId());
        var plan=Map.<String,Object>of("reads",List.of("wrong"),"target","wrong","operation","FAVORITE_ADD","knowledgePoint","tcp");
        var data=assistant.read(owner,plan,page(favoriteOnly));
        assertEquals(2,data.get("total"));
        assertEquals(Set.of(first.getId(),second.getId()),new HashSet<>((List<?>)data.get("_operationQuestionIds")));
        String c=conversation(owner);
        var action=assistant.finalizeActions(owner,c,task(owner),plan,Map.of("page","wrong"),data).get(0);
        assertEquals("PENDING",action.get("status"));assertEquals(2,action.get("count"));
        assertFalse(marks.isFavorite(owner,first.getId()));assertFalse(marks.isFavorite(owner,second.getId()));
        assistant.confirm(owner,c,action.get("id").toString());
        assertTrue(marks.isFavorite(owner,first.getId()));assertTrue(marks.isFavorite(owner,second.getId()));
        assertFalse(marks.isFavorite(owner,noise.getId()));assertFalse(marks.isFavorite(owner,foreign.getId()));
        for(String topic:List.of("TCP协议","传输控制协议")) {
            var aliasPlan=new LinkedHashMap<>(plan);aliasPlan.put("knowledgePoint",topic);
            assertEquals(2,assistant.read(owner,aliasPlan,Map.of()).get("total"));
        }
        var specificPlan=new LinkedHashMap<>(plan);specificPlan.put("knowledgePoint","TCP序号");
        assertEquals(List.of(second.getId()),assistant.read(owner,specificPlan,Map.of()).get("_operationQuestionIds"));
    }

    @Test void collectionPreviewIsCappedAtFiftyAndDoesNotWriteBeforeConfirmation() {
        long owner=owner();
        for(int i=0;i<51;i++) {Question q=question();q.setKnowledgePoint("TCP序号");questions.updateById(q);marks.markWrong(owner,q.getId());}
        var plan=Map.<String,Object>of("reads",List.of("wrong"),"operation","FAVORITE_ADD","target","wrong","knowledgePoint","TCP");
        var data=assistant.read(owner,plan,Map.of());
        assertEquals(51,data.get("total"));assertEquals(20,((List<?>)data.get("items")).size());
        var action=assistant.finalizeActions(owner,conversation(owner),task(owner),plan,Map.of("page","wrong"),data).get(0);
        assertEquals(50,action.get("count"));assertEquals(50,((List<?>)action.get("targets")).size());
        assertTrue(marks.listFavorite(owner).isEmpty());
    }

    @Test void directFavoriteAndPendingOperationsAreIdempotentAndOwned() {
        long owner=owner();Question q=question();String c=conversation(owner),t=task(owner);
        Map<String,Object> plan=Map.of("operation","FAVORITE_ADD","target","selected");
        var action=assistant.finalizeActions(owner,c,t,plan,page(q),Map.of()).get(0);
        assertEquals("SUCCESS",action.get("status"));assertTrue(marks.isFavorite(owner,q.getId()));
        assertEquals(action.get("id"),assistant.finalizeActions(owner,c,t,plan,page(q),Map.of()).get(0).get("id"));
        var pending=assistant.finalizeActions(owner,c,task(owner),Map.of("operation","FAVORITE_REMOVE","target","selected"),page(q),Map.of()).get(0);
        assertTrue(marks.isFavorite(owner,q.getId()));
        ApiException foreign=assertThrows(ApiException.class,()->assistant.confirm(owner+1,c,pending.get("id").toString()));assertEquals(404,foreign.getHttpStatus());
        assertEquals("SUCCESS",assistant.confirm(owner,c,pending.get("id").toString()).get("status"));
        assertEquals("SUCCESS",assistant.confirm(owner,c,pending.get("id").toString()).get("status"));assertFalse(marks.isFavorite(owner,q.getId()));
    }

    @Test void concurrentPracticeConfirmationCreatesOneSessionAndTargetChangesConflict() throws Exception {
        long owner=owner();Question q=question();String c=conversation(owner);
        var a=assistant.finalizeActions(owner,c,task(owner),Map.of("operation","PRACTICE_CREATE","target","selected","count",1),page(q),Map.of()).get(0);
        String id=a.get("id").toString();var pool=Executors.newFixedThreadPool(2);var gate=new CountDownLatch(1);
        try {
            Callable<Map<String,Object>> work=()->{gate.await();return assistant.confirm(owner,c,id);};
            var first=pool.submit(work);var second=pool.submit(work);gate.countDown();
            assertEquals(first.get(15,TimeUnit.SECONDS).get("result"),second.get(15,TimeUnit.SECONDS).get("result"));
            assertEquals(1,practice.listSessions(owner).size());
        }finally{pool.shutdownNow();}
        var pending=assistant.finalizeActions(owner,c,task(owner),Map.of("operation","FAVORITE_REMOVE","target","selected"),page(q),Map.of()).get(0);
        q.setVersion(2);questions.updateById(q);
        ApiException changed=assertThrows(ApiException.class,()->assistant.confirm(owner,c,pending.get("id").toString()));assertEquals(409,changed.getHttpStatus());
        jdbc.update("UPDATE assistant_action SET created_at=? WHERE id=?",LocalDateTime.now().minusDays(31),id);
        assertThrows(ApiException.class,()->assistant.confirm(owner,c,id));
    }

    @Test void statisticsUseValidSubmissionsAcrossMonthAndCurrentMarksStayIndependent() {
        long owner=owner();Question q=question();LocalDate to=LocalDate.of(2026,3,2),from=to.minusDays(29);
        for(int i=0;i<3;i++){
            String s=practice.startSession(owner,q.getSubject(),null,1);practice.answer(owner,s,q.getId(),i==0?"A":"B");
            jdbc.update("UPDATE practice_record SET answered_at=? WHERE session_id=?",from.plusDays(i).atTime(23,50),s);
        }
        String unfinished=practice.startSession(owner,q.getSubject(),null,1);
        jdbc.update("UPDATE practice_record SET grading_status='withdrawn' WHERE user_id=? AND is_correct=0",owner);
        marks.markWrong(owner,q.getId());
        var aggregate=stats.learning(owner,from,to,q.getSubject());
        assertEquals(2,aggregate.get("questionCount"));assertEquals(2,aggregate.get("correctCount"));assertEquals(1L,aggregate.get("uniqueQuestions"));assertEquals(1,aggregate.get("wrongCount"));
        assertEquals(1.0,aggregate.get("accuracy"));assertEquals(2,((List<?>)aggregate.get("daily")).size());
        marks.removeWrong(owner,q.getId());assertEquals(2,stats.learning(owner,from,to,q.getSubject()).get("questionCount"));
        assertEquals(0,stats.learning(owner+1,from,to,q.getSubject()).get("questionCount"));
        assertTrue(practice.sessionSummary(owner,unfinished).get("accuracy").equals(0.0));
    }
    @Test void semanticSingleQuestionRequiresPreviewAndSurvivesStoredContext() throws Exception {
        long owner=owner();Question q=question();q.setKnowledgePoint("遍历");q.setContent("左右孩子的访问顺序");questions.updateById(q);marks.markWrong(owner,q.getId());
        when(search.search(eq("二叉树"),anyList())).thenAnswer(call->{
            List<Map<String,Object>> candidates=call.getArgument(1);assertEquals(List.of(q.getId()),candidates.stream().map(x->x.get("id")).toList());
            assertFalse(candidates.get(0).containsKey("answer"));assertFalse(candidates.get(0).containsKey("analysis"));
            return new QuestionSearchService.Result("READY","synthetic",List.of(Map.of("id",q.getId(),"version",1,"method","SEMANTIC","score",.91)));
        });
        var plan=Map.<String,Object>of("reads",List.of("wrong"),"target","wrong","operation","FAVORITE_ADD","knowledgePoint","二叉树");
        var read=assistant.read(owner,plan,Map.of());
        @SuppressWarnings("unchecked") Map<String,Object> stored=json.readValue(json.writeValueAsString(read),Map.class);
        String conversation=conversation(owner);
        var pending=assistant.finalizeActions(owner,conversation,task(owner),plan,Map.of("page","wrong"),stored).get(0);
        assertEquals("PENDING",pending.get("status"));assertFalse(marks.isFavorite(owner,q.getId()));
        assertEquals("SEMANTIC",((Map<?,?>)((List<?>)pending.get("targets")).get(0)).get("matchMethod"));
        assertEquals("SUCCESS",assistant.confirm(owner,conversation,pending.get("id").toString()).get("status"));
        assertEquals("SUCCESS",assistant.confirm(owner,conversation,pending.get("id").toString()).get("status"));
        assertTrue(marks.isFavorite(owner,q.getId()));
    }

    @Test void indexingFailureCannotFallBackToWholeCollectionAndPublicSearchHidesPersonalAnswers() {
        long owner=owner();Question q=question();marks.markWrong(owner,q.getId());
        var plan=Map.<String,Object>of("reads",List.of("wrong"),"target","wrong","operation","FAVORITE_ADD","knowledgePoint","二叉树");
        for(String state:List.of("BUILDING","BUSY","FAILED","UNAVAILABLE")) {
            when(search.search(anyString(),anyList())).thenReturn(new QuestionSearchService.Result(state,"synthetic",List.of()));
            var read=assistant.read(owner,plan,Map.of());assertEquals(state,read.get("retrievalStatus"));assertEquals(0,read.get("total"));
            assertTrue(assistant.finalizeActions(owner,conversation(owner),task(owner),plan,Map.of(),read).isEmpty());
            assertFalse(marks.isFavorite(owner,q.getId()));
        }
        var publicPlan=Map.<String,Object>of("reads",List.of("questions"),"target","normal");
        String session=practice.startSession(owner,q.getSubject(),null,1);practice.answer(owner,session,q.getId(),"A");
        var read=assistant.read(owner,publicPlan,Map.of("page","wrong","selectedQuestionIds",List.of(q.getId())));
        @SuppressWarnings("unchecked") var items=(List<Map<String,Object>>)read.get("items");
        var found=items.stream().filter(x->q.getContent().equals(x.get("content"))).findFirst().orElseThrow();
        assertEquals("questions",found.get("scope"));assertEquals(false,found.get("answered"));
        assertFalse(found.containsKey("answer"));assertFalse(found.containsKey("userAnswer"));assertFalse(found.containsKey("inWrongBook"));
    }

    @Test void semanticMatchDetectsChangesBeforePreviewAndBeforeConfirmation() {
        long owner=owner();Question q=question();marks.markWrong(owner,q.getId());
        var plan=Map.<String,Object>of("reads",List.of("wrong"),"target","wrong","operation","FAVORITE_ADD","knowledgePoint","进程调度");
        var read=assistant.read(owner,plan,Map.of());q.setVersion(2);questions.updateById(q);
        assertEquals(409,assertThrows(ApiException.class,()->assistant.finalizeActions(owner,conversation(owner),task(owner),plan,Map.of(),read)).getHttpStatus());
        var refreshed=assistant.read(owner,plan,Map.of());String c=conversation(owner);
        var action=assistant.finalizeActions(owner,c,task(owner),plan,Map.of(),refreshed).get(0);
        marks.removeWrong(owner,q.getId());
        assertEquals(409,assertThrows(ApiException.class,()->assistant.confirm(owner,c,action.get("id").toString())).getHttpStatus());
    }

    @Test void focusedReadsAndMixedScopesNeverMislabelPrivateWrongAttempts() {
        long owner=owner();Question wrong=question(),favorite=question();
        String old=practice.startSession(owner,wrong.getSubject(),null,1);practice.answer(owner,old,wrong.getId(),"A");
        marks.toggleFavorite(owner,favorite.getId(),true);
        var mixed=assistant.read(owner,Map.of("reads",List.of("wrong","favorite")),Map.of("page","favorite"));
        @SuppressWarnings("unchecked") var items=(List<Map<String,Object>>)mixed.get("items");
        assertTrue(items.stream().anyMatch(x->"wrong".equals(x.get("scope"))&&Boolean.TRUE.equals(x.get("answered"))));
        assertTrue(items.stream().anyMatch(x->"favorite".equals(x.get("scope"))&&Boolean.FALSE.equals(x.get("answered"))));
        var focused=assistant.read(owner,Map.of("reads",List.of("wrong"),"target","selected"),Map.of("page","wrong","selectedQuestionIds",List.of(wrong.getId())));
        assertEquals(1,focused.get("total"));
        String fresh=practice.startSession(owner,wrong.getSubject(),null,1);
        var unanswered=assistant.read(owner,Map.of("reads",List.of("practice"),"target","selected"),Map.of("page","practice","sessionId",fresh,"selectedQuestionIds",List.of(wrong.getId())));
        assertEquals(false,item(unanswered).get("answered"));assertFalse(item(unanswered).containsKey("answer"));
    }
}
