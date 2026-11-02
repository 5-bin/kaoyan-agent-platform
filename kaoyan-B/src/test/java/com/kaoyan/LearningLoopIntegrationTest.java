package com.kaoyan;

import com.kaoyan.learning.*;
import com.kaoyan.learning.LearningContracts.*;
import com.kaoyan.entity.*;
import com.kaoyan.mapper.*;
import com.kaoyan.service.*;
import com.kaoyan.security.JwtService;
import com.kaoyan.feign.AgentFeignClient;
import com.kaoyan.dto.agent.*;
import com.fasterxml.jackson.databind.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties={
 "spring.datasource.driver-class-name=org.h2.Driver",
 "spring.datasource.url=jdbc:h2:mem:learning-loop;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER",
 "spring.datasource.username=sa","spring.datasource.password=",
 "spring.sql.init.mode=always","spring.sql.init.schema-locations=classpath:schema-test.sql,classpath:schema-practice.sql,classpath:schema-learning-test.sql",
 "jwt.secret=test-only-jwt-key-at-least-32-characters","kaoyan.agent.internal-key=test-only-internal-key-12345",
 "kaoyan.agent.base-url=http://127.0.0.1:9", "oss.endpoint=","oss.access-key-id=",
 "kaoyan.learning.enabled=true","kaoyan.learning.initial-delay-ms=3600000"
})
@AutoConfigureMockMvc
class LearningLoopIntegrationTest {
 @Autowired MockMvc mvc; @Autowired ObjectMapper json; @Autowired QuestionMapper questions;
 @Autowired PracticeRecordMapper records; @Autowired JdbcTemplate jdbc; @Autowired JwtService jwt;
 @Autowired ManagedPracticeService practice; @Autowired LearningProfiles profiles; @Autowired LearningWorker worker;
 @Autowired LearningRecommendations recommendations; @Autowired TransactionTemplate tx;
 @Autowired TaskMapper tasks;
 @Autowired AssistantLearningService assistant;
 @MockitoBean AgentFeignClient agent; @MockitoBean StringRedisTemplate redis;
 final String release="rag-v1-0123456789abcdef";
 JsonNode call(MockHttpServletRequestBuilder req,String token,Object body,int status) throws Exception {
  if(token!=null)req.header("Authorization","Bearer "+token);
  if(body!=null)req.contentType("application/json").content(json.writeValueAsString(body));
  var response=mvc.perform(req).andExpect(status().is(status)).andReturn().getResponse().getContentAsString();
  return json.readTree(response).path("data");
 }
 String login() throws Exception {
  var body=Map.of("username","s"+UUID.randomUUID().toString().replace("-","").substring(0,15),"password","test-password");
  call(post("/api/auth/register"),null,body,200);return call(post("/api/auth/login"),null,body,200).path("accessToken").asText();
 }
 long owner(String token) {return Long.parseLong(jwt.parse(token).getSubject());}
 Question question(String subject,String point) {
  var q=new Question();q.setSubject(subject);q.setKnowledgePoint(point);q.setContent("测试题干");q.setOptionA("选项A");q.setOptionB("选项B");q.setOptionC("选项C");q.setOptionD("选项D");
  q.setAnswer("B");q.setAnalysis("审核解析");q.setActive(1);q.setVersion(1);q.setDifficulty("EASY");q.setReviewStatus("APPROVED");q.setQuestionType("SINGLE_CHOICE");q.setStableOrder(0);
  questions.insert(q);return q;
 }
 String start(String token,Question... qs) throws Exception {
  return call(post("/api/practice/sessions"),token,Map.of("count",qs.length,"questionIds",Arrays.stream(qs).map(Question::getId).toList()),200).path("sessionId").asText();
 }
 Map<String,Object> answer(Question q,long item,String key,String choice) {return Map.of("questionId",q.getId(),"itemId",item,"clientRequestId",key,"answer",choice);}
 long item(String session,long user) {return practice.state(user,session).items().get(0).itemId();}
 @Test void assistantConfirmationFitsExistingSessionColumnAndCreatesOneManagedBatch() throws Exception {
  String token=login();long user=owner(token);var q=question("数据结构",UUID.randomUUID().toString());
  String conversation=UUID.randomUUID().toString(),task=UUID.randomUUID().toString();
  jdbc.update("INSERT INTO chat_conversation(id,user_id,title,conditions_json,profile_json) VALUES(?,?,'隔离组题','{}','{}')",conversation,user);
  jdbc.update("INSERT INTO task(id,user_id,task_type,status,created_at) VALUES(?,?,'CHAT','SUCCESS',CURRENT_TIMESTAMP)",task,user);
  var plan=Map.<String,Object>of("operation","PRACTICE_CREATE","target","selected","count",5);
  var page=Map.<String,Object>of("page","practice","selectedQuestionIds",List.of(q.getId()),"visibleQuestionIds",List.of(q.getId()));
  var action=assistant.finalizeActions(user,conversation,task,plan,page,Map.of()).get(0);
  assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM practice_record WHERE user_id=?",Integer.class,user));
  String actionId=action.get("id").toString();
  JsonNode confirmed=json.valueToTree(assistant.confirm(user,conversation,actionId));
  String session=confirmed.path("result").path("sessionId").asText();
  assertTrue(session.startsWith("L-"));assertTrue(session.length()<=36);
  assertEquals("SUCCESS",confirmed.path("status").asText());
  assertEquals(confirmed,json.valueToTree(assistant.confirm(user,conversation,actionId)));
  assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM practice_record WHERE user_id=?",Integer.class,user));
  var state=call(get("/api/practice/sessions/"+session+"/state"),token,null,200);
  assertEquals(1,state.path("items").size());assertTrue(state.path("items").get(0).path("answer").isNull());
 }
 @Test void draftsAndReplayAndFormalFinishArePersistent() throws Exception {
  var token=login();long user=owner(token);var q=question("数据结构",UUID.randomUUID().toString());var q2=question("数据结构",UUID.randomUUID().toString());String s=start(token,q,q2);long item=item(s,user);
  var progress=call(put("/api/practice/sessions/"+s+"/progress"),token,Map.of("revision",0,"currentIndex",0,"answers",Map.of(""+item,"B")),200);
  assertEquals("B",progress.path("items").get(0).path("draftAnswer").asText());assertEquals(0,call(get("/api/stats/overview"),token,null,200).path("totalQuestions").asInt());
  call(put("/api/practice/sessions/"+s+"/progress"),token,Map.of("revision",0,"currentIndex",0,"answers",Map.of()),409);
  var body=answer(q,item,"same-request","B");var first=call(post("/api/practice/sessions/"+s+"/answer"),token,body,200);
  assertEquals(first,call(post("/api/practice/sessions/"+s+"/answer"),token,body,200));
  call(post("/api/practice/sessions/"+s+"/answer"),token,answer(q,item,"same-request","A"),409);
  call(post("/api/practice/sessions/"+s+"/answer"),token,answer(q,item,"different-request","B"),409);
  var finished=call(post("/api/practice/sessions/"+s+"/finish"),token,null,200);assertEquals(1,finished.path("answered").asInt());assertEquals(1,finished.path("unanswered").asInt());
  assertEquals(finished,call(post("/api/practice/sessions/"+s+"/finish"),token,null,200));
  call(put("/api/practice/sessions/"+s+"/progress"),token,Map.of("revision",2,"currentIndex",0,"answers",Map.of()),409);
  worker.tick();assertEquals(1,profiles.profile(user).independentSamples());int rev=profiles.profile(user).revision();worker.tick();assertEquals(rev,profiles.profile(user).revision());
 }
 @Test void diagnosisWithholdsAllGradingUntilFinish() throws Exception {
  var token=login();long user=owner(token);question("数据结构",UUID.randomUUID().toString());
  String s=call(post("/api/diagnostics/sessions"),token,null,200).path("sessionId").asText();var state=practice.state(user,s);
  assertFalse(state.blueprint().isEmpty());var first=state.items().get(0);
  // Keep at least one item pending so this is an unfinished diagnostic.
  if(state.items().size()==1) {question("操作系统",UUID.randomUUID().toString());s=call(post("/api/diagnostics/sessions"),token,null,200).path("sessionId").asText();state=practice.state(user,s);first=state.items().get(0);}
  // The shared fixture can include revisions from other tests; answer the selected version, not an assumed B.
  String expected=jdbc.queryForObject("SELECT answer FROM question WHERE id=?",String.class,first.questionId());
  var body=Map.of("questionId",first.questionId(),"itemId",first.itemId(),"answer",expected,"clientRequestId","diag-first");
  var response=call(post("/api/practice/sessions/"+s+"/answer"),token,body,200);assertTrue(response.path("isCorrect").isNull());assertTrue(response.path("answer").isNull());
  assertEquals(0,call(get("/api/stats/overview"),token,null,200).path("totalQuestions").asInt());
  assertTrue(call(get("/api/practice/sessions/"+s),token,null,200).get(0).path("isCorrect").isNull());
  var review=call(get("/api/practice/sessions/"+s+"/review"),token,null,200).path("list");for(var r:review) {assertFalse(r.has("answer"));assertFalse(r.has("analysis"));}
  assertNull(practice.result(user,s).get("diagnosticReferenceScore"));
  call(post("/api/practice/sessions/"+s+"/finish"),token,null,200);assertEquals(1,call(get("/api/stats/overview"),token,null,200).path("totalQuestions").asInt());
  assertEquals(1,practice.state(user,s).items().get(0).isCorrect());
 }
 @Test void crossAccountAndAdminBoundaries() throws Exception {
  var token=login();var other=login();var q=question("操作系统",UUID.randomUUID().toString());String s=start(token,q);
  for(String suffix:List.of("state","result"))call(get("/api/practice/sessions/"+s+"/"+suffix),other,null,404);
  call(post("/api/practice/sessions/"+s+"/finish"),other,null,404);
  call(post("/api/questions/admin/"+q.getId()+"/versions/1/withdraw"),token,Map.of("reason","测试"),403);
  call(get("/api/learning/profile"),null,null,401);
  call(put("/api/learning/recommendation-settings"),token,Map.of("revision",0,"enabled",true,"preferences",Map.of("ownerId",owner(other))),400);
 }
 @Test void rollbackDoesNotPublishLearningEvidence() throws Exception {
  var token=login();long user=owner(token);var q=question("计算机网络",UUID.randomUUID().toString());String s=start(token,q);long item=item(s,user);
  assertThrows(IllegalStateException.class,()->tx.executeWithoutResult(status -> {practice.submit(user,s,q.getId(),item,"rollback","A");throw new IllegalStateException("rollback");}));
  assertNull(records.selectById(item).getIsCorrect());assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM learning_event WHERE user_id=?",Integer.class,user));
 }
 @Test void overlappingIdenticalRequestsReplayOneResult() throws Exception {
  var token=login();long user=owner(token);var q=question("数据结构",UUID.randomUUID().toString());String s=start(token,q);long item=item(s,user);
  var pool=Executors.newFixedThreadPool(2);var gate=new CountDownLatch(1);
  try {Callable<Submission> work=()->{gate.await();return practice.submit(user,s,q.getId(),item,"parallel","B");};var a=pool.submit(work);var b=pool.submit(work);gate.countDown();assertEquals(a.get(20,TimeUnit.SECONDS),b.get(20,TimeUnit.SECONDS));}
  finally {pool.shutdownNow();}
  assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM practice_request WHERE user_id=?",Integer.class,user));
  worker.tick();assertEquals(1,profiles.profile(user).independentSamples());
 }
 @Test void deletionFinishesWithoutErasingHistoryAndWithdrawalRebuilds() throws Exception {
  var token=login();long user=owner(token);var q=question("数据结构",UUID.randomUUID().toString());String s=start(token,q);
  practice.submit(user,s,q.getId(),item(s,user),"withdraw-answer","A");worker.tick();assertEquals(1,profiles.profile(user).independentSamples());
  call(delete("/api/practice/sessions/"+s),token,null,200);assertEquals(1,practice.state(user,s).items().size());
  practice.withdraw(q.getId(),1,"标准答案有误，撤回测试");worker.tick();assertEquals(0,profiles.profile(user).independentSamples());
  assertEquals(0,call(get("/api/stats/overview"),token,null,200).path("totalQuestions").asInt());assertTrue(practice.state(user,s).items().get(0).withdrawn());
 }
 AgentResponse rules(AgentRequest req) {
  var response=new AgentResponse();response.setTaskId(req.getTaskId());response.setStatus("SUCCESS");response.setReleaseId(release);response.setReferences(List.of());
  response.setResult(Map.of("outcome","NEEDS_INPUT","answer","请补充推荐条件","explanationMode","rules","resolvedTaskType","SCHOOL_RECOMMEND","releaseId",release,"candidates",List.of()));return response;
 }
 void setupRecommendation(long user) {
  profiles.ensure(user);recommendations.save(user,new Settings(0,true,Map.of("majorCodes",List.of("081200"),"degreeType","academic")));
 }
 @Test void automaticRulesNeedNoBrowserSessionAndReuseQuotaOnRetry() throws Exception {
  long user=owner(login());setupRecommendation(user);
  when(agent.chat(anyString(),any())).thenAnswer(c->{AgentRequest req=c.getArgument(1);assertEquals(false,req.getPrivacy().get("modelAllowed"));assertEquals(false,req.getPreferences().get("explainWithAi"));return rules(req);});
  recommendations.run(user,release);var settings=recommendations.settings(user);assertNotNull(settings.get("lastTaskId"));assertEquals("CURRENT",settings.get("status"));
  recommendations.run(user,release);assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM task WHERE user_id=?",Integer.class,user));
  assertEquals(2,((Number)tasks.selectById(settings.get("lastTaskId").toString()).getResultPayload().get("resultSchemaVersion")).intValue());
 }
 @Test void interruptedAndFailedRemoteCallReusesReservedTask() throws Exception {
  long user=owner(login());setupRecommendation(user);
  when(agent.chat(anyString(),any())).thenThrow(new RuntimeException("test-only provider failure"));recommendations.run(user,release);
  assertEquals("PENDING",recommendations.settings(user).get("status"));
  jdbc.update("UPDATE learning_recommendation_settings SET not_before=?,run_until=NULL WHERE user_id=?",ManagedPracticeService.now().minusSeconds(1),user);
  doAnswer(c->rules(c.getArgument(1))).when(agent).chat(anyString(),any());recommendations.run(user,release);
  assertNotNull(recommendations.settings(user).get("lastTaskId"));assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM task WHERE user_id=?",Integer.class,user));
 }
 @Test void newerSettingsPreventOldResultBecomingCurrent() throws Exception {
  long user=owner(login());setupRecommendation(user);
  when(agent.chat(anyString(),any())).thenAnswer(c->{var current=recommendations.settings(user);recommendations.save(user,new Settings(((Number)current.get("revision")).intValue(),false,Map.of()));return rules(c.getArgument(1));});
  recommendations.run(user,release);assertNull(recommendations.settings(user).get("lastTaskId"));assertEquals(false,recommendations.settings(user).get("enabled"));
 }
 @Test void unavailableHintsDoNotMarkIndependentWorkAsAssisted() throws Exception {
  var token=login();long user=owner(token);var q=question("数据结构",UUID.randomUUID().toString());String s=start(token,q);
  assertEquals(false,practice.hint(user,s,item(s,user),1).get("available"));
  practice.submit(user,s,q.getId(),item(s,user),"no-hint","B");worker.tick();assertEquals(1,profiles.profile(user).independentSamples());
 }

 @Test void publishedRevisionKeepsOldSnapshotAndHintsMarkAssistance() throws Exception {
  var token=login();long user=owner(token);var q=question("数据结构",UUID.randomUUID().toString());String original=start(token,q);
  var replacement=new com.kaoyan.dto.request.QuestionUpdateRequest(1,"数据结构",q.getKnowledgePoint(),"EASY","修订后题干","新A","新B","新C","新D","A","新版解析","ORIGINAL","自编审核题","版本2",null,null,"原创许可");
  var published=practice.publishRevision(q.getId(),new Revision(replacement,new Hints("先回顾定义，不看选项结论","比较边界条件"),"已人工核对答案与提示"),user);
  assertEquals(3,((Number)published.get("version")).intValue());
  assertEquals("测试题干",practice.state(user,original).items().get(0).content());
  practice.submit(user,original,q.getId(),item(original,user),"old-version","B");
  assertEquals(1,practice.state(user,original).items().get(0).isCorrect());
  String newer=start(token,q);long current=item(newer,user);
  assertThrows(com.kaoyan.common.ApiException.class,()->practice.hint(user,newer,current,2));
  assertEquals(true,practice.hint(user,newer,current,1).get("available"));
  assertEquals(1,((Number)practice.hint(user,newer,current,1).get("hintLevelUsed")).intValue());
  practice.submit(user,newer,q.getId(),current,"new-version","A");worker.tick();
  assertEquals(1,profiles.profile(user).independentSamples());assertEquals(1,profiles.profile(user).assistedSamples());
  practice.withdraw(q.getId(),1,"修订旧版本依据");worker.tick();assertEquals(0,profiles.profile(user).independentSamples());
  assertEquals(1,practice.state(user,newer).items().get(0).isCorrect());
 }
 @Test void quotaFailureDoesNotCreateOrLoseAutomaticWork() throws Exception {
  long user=owner(login());setupRecommendation(user);
  for(int i=0;i<6;i++)jdbc.update("INSERT INTO task(id,user_id,task_type,status,created_at,updated_at) VALUES(?,?,'CHAT','SUCCESS',?,?)",UUID.randomUUID().toString(),user,ManagedPracticeService.now(),ManagedPracticeService.now());
  var failure=assertThrows(com.kaoyan.common.ApiException.class,()->recommendations.run(user,release));assertEquals(429,failure.getHttpStatus());
  assertEquals("PENDING",recommendations.settings(user).get("status"));assertEquals(6,jdbc.queryForObject("SELECT COUNT(*) FROM task WHERE user_id=?",Integer.class,user));
 }
 @Test void historicalMetricComparisonUsesOnlySameScopeAndNeverRemovesCandidates() throws Exception {
  long user=owner(login());var source=Map.<String,Object>of("title","测试来源","url","https://github.com/example/official-test","locator","测试定位","version","1","retrievedAt","2026-10-25","permissionNote","测试夹具");
  recommendations.addMetric(new Metric("test-program","测试学校","计算机学院","081200",2026,"TOTAL_CUTOFF",null,500,350.0,source),user);
  var candidate=Map.<String,Object>of("programId","test-program","school","测试学校","college","计算机学院","majorCode","081200","year",2027,"examSubjects",List.of("101","201","301","408"));
  var result=new LinkedHashMap<String,Object>();result.put("candidates",List.of(candidate));var snap=new LinkedHashMap<String,Object>();snap.put("referenceScore",90);
  recommendations.enrich(user,result,snap,"MANUAL");assertEquals("NO_COMPARABLE_DATA",((Map<?,?>)((List<?>)result.get("historicalComparisons")).get(0)).get("status"));
  recommendations.addMetric(new Metric("test-program","测试学校","计算机学院","081200",2026,"SUBJECT_CUTOFF","408",150,95.0,source),user);
  recommendations.enrich(user,result,snap,"MANUAL");var comparison=(Map<?,?>)((List<?>)result.get("historicalComparisons")).get(0);
  assertEquals(-5.0,comparison.get("gap"));assertEquals(1,((List<?>)result.get("candidates")).size());
 }

 @Test void changedExamYearDuringGenerationCannotPublishOldCandidatesAsCurrent() throws Exception {
  long user=owner(login());setupRecommendation(user);
  when(agent.chat(anyString(),any())).thenAnswer(c->{jdbc.update("UPDATE `user` SET exam_year=2028 WHERE id=?",user);return rules(c.getArgument(1));});
  recommendations.run(user,release);assertNull(recommendations.settings(user).get("lastTaskId"));assertEquals("CONDITIONS_CHANGED",recommendations.settings(user).get("pendingReason"));
 }
}
