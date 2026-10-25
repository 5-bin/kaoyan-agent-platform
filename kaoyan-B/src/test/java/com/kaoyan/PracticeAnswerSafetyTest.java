package com.kaoyan;

import com.fasterxml.jackson.databind.*;
import com.kaoyan.entity.*;
import com.kaoyan.mapper.*;
import com.kaoyan.security.JwtService;
import com.kaoyan.feign.AgentFeignClient;
import com.kaoyan.dto.agent.AgentRequest;
import com.kaoyan.dto.agent.AgentResponse;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties={
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.url=jdbc:h2:mem:answer-safety;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER",
    "spring.datasource.username=sa", "spring.datasource.password=",
    "spring.sql.init.mode=always", "spring.sql.init.schema-locations=classpath:schema-test.sql,classpath:schema-practice.sql",
    "jwt.secret=test-only-jwt-key-at-least-32-characters",
    "kaoyan.agent.internal-key=test-only-internal-key-12345", "oss.endpoint=", "oss.access-key-id="
})
@AutoConfigureMockMvc
class PracticeAnswerSafetyTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired QuestionMapper questions;
    @Autowired PracticeRecordMapper records;
    @Autowired JdbcTemplate jdbc;
    @Autowired JwtService jwt;
    @MockitoBean AgentFeignClient agent;
    @MockitoBean StringRedisTemplate redis;

    JsonNode call(MockHttpServletRequestBuilder req, String token, Object body, int statusCode) throws Exception {
        if (token != null) req.header("Authorization", "Bearer "+token);
        if (body != null) req.contentType("application/json").content(json.writeValueAsString(body));
        String text = mvc.perform(req).andExpect(status().is(statusCode)).andReturn().getResponse().getContentAsString();
        return text.isBlank() ? json.nullNode() : json.readTree(text).path("data");
    }
    String login() throws Exception {
        var body=Map.of("username","s"+UUID.randomUUID().toString().replace("-", "").substring(0,15),"password","test-password");
        call(post("/api/auth/register"),null,body,200);
        return call(post("/api/auth/login"),null,body,200).path("accessToken").asText();
    }
    long owner(String token) { return Long.parseLong(jwt.parse(token).getSubject()); }
    Question question() {
        var q=new Question(); q.setSubject("s"+UUID.randomUUID().toString().substring(0,8)); q.setKnowledgePoint("测试知识点");
        q.setContent("原题干"); q.setOptionA("原选项A"); q.setOptionB("原选项B"); q.setOptionC("原选项C"); q.setOptionD("原选项D");
        q.setAnswer("B"); q.setAnalysis("原解析"); q.setActive(1); q.setVersion(1); q.setDifficulty("EASY");
        q.setReviewStatus("APPROVED"); q.setReviewComment("private-review"); q.setQuestionType("SINGLE_CHOICE"); q.setStableOrder(0);
        questions.insert(q); return q;
    }
    String start(String token, Question q) throws Exception {
        return call(post("/api/practice/sessions"),token,Map.of("subject",q.getSubject(),"count",1),200).path("sessionId").asText();
    }
    JsonNode answer(String token,String session,Question q,String option,int status) throws Exception {
        return call(post("/api/practice/sessions/"+session+"/answer"),token,Map.of("questionId",q.getId(),"answer",option),status);
    }
    JsonNode review(String token,String session) throws Exception {
        return call(get("/api/practice/sessions/"+session+"/review"),token,null,200).path("list").get(0);
    }
    void hidden(JsonNode node) {
        assertNotNull(node);
        if (node.isObject()) for (String key:List.of("answer","analysis","questionSnapshot","reviewComment","reviewerUserId"))
            assertFalse(node.has(key),"unexpected field: "+key+" in "+node);
        node.forEach(this::hidden);
    }
    @Test void allUnansweredStudentRoutesHideSecretsEvenAfterManualMarks() throws Exception {
        String token=login(); var q=question(); String session=start(token,q);
        // Defensive DTO: even a stray snapshot attached to an unanswered row is not serialized.
        var row=records.selectList(null).stream().filter(r->session.equals(r.getSessionId())).findFirst().orElseThrow();
        row.setQuestionSnapshot(Map.of("id",q.getId(),"answer","B","analysis","secret")); records.updateById(row);
        call(post("/api/marks/wrong/"+q.getId()),token,null,200);
        call(post("/api/marks/favorite/"+q.getId()),token,null,200);
        for(String path:List.of("/api/questions/"+q.getId(),"/api/questions/practice?subject="+q.getSubject(),
            "/api/practice/sessions/"+session,"/api/practice/sessions/"+session+"/review","/api/marks/wrong","/api/marks/favorite"))
            hidden(call(get(path),token,null,200));
        assertEquals("NOT_ANSWERED",review(token,session).path("snapshotStatus").asText());
        call(get("/api/questions/"+q.getId()),null,null,401);
        call(get("/api/questions/admin/pending"),token,null,403);
        q.setActive(0); questions.updateById(q);
        call(get("/api/questions/"+q.getId()),token,null,404);
        hidden(review(token,session));
        q.setActive(1);q.setReviewStatus("PENDING_REVIEW");questions.updateById(q);
        call(get("/api/questions/"+q.getId()),token,null,404);
    }
    @Test void savedServerResultAndHistorySurviveQuestionEditsAndDeletion() throws Exception {
        String token=login(),other=login(); var q=question(); String session=start(token,q);
        JsonNode result=answer(token,session,q," a ",200);
        assertEquals(0,result.path("isCorrect").asInt()); assertEquals("A",result.path("userAnswer").asText());
        assertEquals("B",result.path("answer").asText()); assertEquals("原解析",result.path("analysis").asText());
        call(post("/api/marks/favorite/"+q.getId()),token,null,200);
        q.setContent("新题干");q.setOptionA("新选项A");q.setAnswer("A");q.setAnalysis("新解析");q.setVersion(2);questions.updateById(q);
        for(String path:List.of("/api/practice/sessions/"+session+"/review","/api/marks/wrong","/api/marks/favorite")) {
            JsonNode item=call(get(path),token,null,200).path("list").get(0);
            assertEquals("原题干",item.path("content").asText());assertEquals("原选项A",item.path("optionA").asText());
            assertEquals("B",item.path("answer").asText());assertEquals("原解析",item.path("analysis").asText());
            assertEquals("AVAILABLE",item.path("snapshotStatus").asText());
        }
        call(post("/api/marks/favorite/"+q.getId()),other,null,200);
        hidden(call(get("/api/marks/favorite"),other,null,200));
        hidden(call(get("/api/questions/"+q.getId()),token,null,200));
        questions.deleteById(q.getId());
        assertEquals("B",review(token,session).path("answer").asText());
    }
    @Test void invalidForeignAndDuplicateAnswersDoNotAccumulate() throws Exception {
        String token=login(),other=login(); var q=question();
        q.setOptionD(null); jdbc.update("UPDATE question SET option_d=NULL WHERE id=?",q.getId());
        String session=start(token,q);
        for(String invalid:List.of("E","AB","","任意内容")) answer(token,session,q,invalid,400);
        q.setOptionD(null); jdbc.update("UPDATE question SET option_d=NULL WHERE id=?",q.getId());
        answer(token,session,q,"D",400);
        answer(other,session,q,"A",404);
        call(get("/api/practice/sessions/"+session),other,null,404);
        call(get("/api/practice/sessions/"+session+"/review"),other,null,404);
        assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM study_stat WHERE user_id=?",Integer.class,owner(token)));
        assertTrue(review(token,session).path("isCorrect").isNull());
        JsonNode result=answer(token,session,q,"b",200);assertEquals(1,result.path("isCorrect").asInt());
        answer(token,session,q,"B",409);answer(token,session,q,"A",409);
        assertEquals(1,jdbc.queryForObject("SELECT question_count FROM study_stat WHERE user_id=?",Integer.class,owner(token)));
        assertEquals(1,jdbc.queryForObject("SELECT correct_count FROM study_stat WHERE user_id=?",Integer.class,owner(token)));
    }
    @Test void missingAndPartialLegacySnapshotsNeverFallbackToCurrentAnswers() throws Exception {
        String token=login();var q=question();String session=start(token,q);answer(token,session,q,"A",200);
        call(post("/api/marks/favorite/"+q.getId()),token,null,200);
        var row=records.selectList(null).stream().filter(r->session.equals(r.getSessionId())).findFirst().orElseThrow();
        for(String value:Arrays.asList(null,"{}")) {
            jdbc.update("UPDATE practice_record SET question_snapshot=? WHERE id=?",value,row.getId());
            var view=review(token,session);assertEquals("MISSING",view.path("snapshotStatus").asText()); hidden(view);
            hidden(call(get("/api/marks/wrong"),token,null,200));hidden(call(get("/api/marks/favorite"),token,null,200));
        }
        row.setQuestionSnapshot(Map.of("id",q.getId(),"subject",q.getSubject(),"content","旧快照题干","answer","C","analysis","旧解析","version",1));
        records.updateById(row);
        var partial=review(token,session);assertEquals("PARTIAL",partial.path("snapshotStatus").asText());
        assertEquals("C",partial.path("answer").asText());assertTrue(partial.path("optionA").isNull());
        String newer=start(token,q);answer(token,newer,q,"A",200);
        jdbc.update("UPDATE practice_record SET question_snapshot=NULL WHERE session_id=?",newer);
        assertEquals("MISSING",call(get("/api/marks/favorite"),token,null,200).path("list").get(0).path("snapshotStatus").asText());
    }
    @Test void overlappingSubmissionsHaveOneWinnerAndOneStatisticsUpdate() throws Exception {
        String token=login();var q=question();String session=start(token,q);
        var pool=Executors.newFixedThreadPool(2);var gate=new CountDownLatch(1);
        try {
            Callable<Integer> run=()-> { assertTrue(gate.await(10,TimeUnit.SECONDS)); return mvc.perform(post("/api/practice/sessions/"+session+"/answer")
                .header("Authorization","Bearer "+token).contentType("application/json")
                .content(json.writeValueAsString(Map.of("questionId",q.getId(),"answer","A")))).andReturn().getResponse().getStatus(); };
            var a=pool.submit(run);var b=pool.submit(run);gate.countDown();
            var outcomes=new ArrayList<>(List.of(a.get(20,TimeUnit.SECONDS),b.get(20,TimeUnit.SECONDS)));Collections.sort(outcomes);
            assertEquals(List.of(200,409),outcomes);
        } finally {pool.shutdownNow();}
        assertEquals(1,jdbc.queryForObject("SELECT question_count FROM study_stat WHERE user_id=?",Integer.class,owner(token)));
        assertEquals(1,jdbc.queryForObject("SELECT wrong_count FROM user_question_mark WHERE user_id=? AND question_id=?",Integer.class,owner(token),q.getId()));
    }
    @Test void expandedDisplaySnapshotDoesNotChangePythonPayload() throws Exception {
        String token=login();var q=question();String session=start(token,q);answer(token,session,q,"B",200);
        when(agent.chat(anyString(),any())).thenAnswer(call->{
            AgentRequest request=call.getArgument(1);var supplied=request.getQuestions().get(0);
            assertEquals(Set.of("id","version","subject","knowledgePoint","content","answer","analysis","correct"),supplied.keySet());
            var response=new AgentResponse();response.setTaskId(request.getTaskId());response.setStatus("FAILED");return response;
        });
        call(post("/api/practice/sessions/"+session+"/ai-summary"),token,null,200);
        verify(agent).chat(anyString(),any());
    }
}
