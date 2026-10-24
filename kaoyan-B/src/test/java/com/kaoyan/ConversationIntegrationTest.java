package com.kaoyan;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.service.ConversationService;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import java.io.*;
import java.net.*;
import java.net.http.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;

/** Actual browser-facing HTTP -> Java -> FastAPI -> LangChain -> controlled SDK wire. */
@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT, properties={
    "spring.datasource.url=jdbc:h2:mem:conversation;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER",
    "spring.datasource.driver-class-name=org.h2.Driver","spring.datasource.username=sa","spring.datasource.password=",
    "spring.sql.init.mode=always","spring.sql.init.schema-locations=classpath:schema-chain.sql,classpath:schema-practice.sql",
    "jwt.secret=test-only-jwt-secret-0123456789abcdefghijklmnopqrstuvwxyz",
    "kaoyan.agent.internal-key=test-only-internal-key-123456"
})
@ExtendWith(OutputCaptureExtension.class)
class ConversationIntegrationTest {
    @LocalServerPort int port;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate jdbc;
    @Autowired ConversationService service;
    @MockitoBean StringRedisTemplate redis;
    static Process python;
    static final HttpClient HTTP=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

    @DynamicPropertySource static void python(DynamicPropertyRegistry properties) throws Exception {
        int port;
        try(var socket=new ServerSocket(0,0,InetAddress.getLoopbackAddress())) { port=socket.getLocalPort(); }
        var builder=new ProcessBuilder(System.getenv().getOrDefault("PYTHON_EXECUTABLE","python"),"-m","uvicorn","tests.chat_wire_app:app","--host","127.0.0.1","--port",String.valueOf(port));
        builder.directory(Path.of("..","kaoyan-agent").toAbsolutePath().normalize().toFile());
        builder.environment().put("AGENT_INTERNAL_KEY","test-only-internal-key-123456");
        builder.environment().put("LANGCHAIN_TRACING_V2","false");
        builder.redirectErrorStream(true).redirectOutput(Path.of("target","chat-python.log").toFile());
        python=builder.start();
        String base="http://127.0.0.1:"+port;
        for(int i=0;i<100 && python.isAlive();i++) {
            try {
                if(HTTP.send(HttpRequest.newBuilder(URI.create(base+"/health")).timeout(Duration.ofSeconds(1)).build(),HttpResponse.BodyHandlers.discarding()).statusCode()==200) {
                    properties.add("kaoyan.agent.base-url",()->base); return;
                }
            } catch(Exception ignored) {}
            Thread.sleep(100);
        }
        throw new IllegalStateException("隔离Python未启动，查看target/chat-python.log");
    }
    @AfterAll static void cleanup() throws Exception {
        if(python!=null) { python.destroy(); if(!python.waitFor(5,TimeUnit.SECONDS)) python.destroyForcibly(); }
    }
    HttpRequest.Builder request(String token,String path) {
        var builder=HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+"/api"+path)).timeout(Duration.ofSeconds(10)).header("Content-Type","application/json");
        if(token!=null) builder.header("Authorization","Bearer "+token);
        return builder;
    }
    JsonNode call(String token,String method,String path,Object body,int expected) throws Exception {
        var builder=request(token,path).method(method,body==null?HttpRequest.BodyPublishers.noBody():HttpRequest.BodyPublishers.ofString(json.writeValueAsString(body)));
        var response=HTTP.send(builder.build(),HttpResponse.BodyHandlers.ofString());
        assertEquals(expected,response.statusCode(),path+" "+response.body());
        return json.readTree(response.body()).path("data");
    }
    String account() throws Exception {
        var input=Map.of("username","chat"+UUID.randomUUID().toString().substring(0,8),"password","test-password");
        call(null,"POST","/auth/register",input,200);
        String token=call(null,"POST","/auth/login",input,200).path("accessToken").asText();
        var settings=call(token,"GET","/privacy/settings",null,200);
        call(token,"PUT","/privacy/settings",Map.of("modelAllowed",true,"scopes",List.of("wrong","favorite","stats","profile","document"),"provider",settings.path("provider").asText()),200);
        return token;
    }
    String privateAccount() throws Exception {
        var input=Map.of("username","private"+UUID.randomUUID().toString().substring(0,8),"password","test-password");
        call(null,"POST","/auth/register",input,200);
        return call(null,"POST","/auth/login",input,200).path("accessToken").asText();
    }
    String conversation(String token) throws Exception { return call(token,"POST","/conversations",null,200).path("id").asText(); }
    JsonNode send(String token,String id,String query,String requestId) throws Exception {
        return call(token,"POST","/conversations/"+id+"/messages",Map.of("query",query,"clientRequestId",requestId),200);
    }
    JsonNode latest(String token,String id) throws Exception {
        var attempts=call(token,"GET","/conversations/"+id+"/messages",null,200).path("list").get(0).path("attempts");
        return attempts.get(attempts.size()-1);
    }
    JsonNode finish(String token,String id) throws Exception {
        for(int i=0;i<160;i++) {
            var value=latest(token,id);
            if(!value.path("status").asText().equals("RUNNING")) {
                String state=value.path("result").path("retrievalStatus").asText();
                if(Set.of("BUILDING","BUSY").contains(state)) {
                    // First request truthfully reports warm-up; retry only in this test helper.
                    assertTrue(value.path("result").path("actions").isEmpty());Thread.sleep(100);
                    var message=call(token,"GET","/conversations/"+id+"/messages",null,200).path("list").get(0);
                    call(token,"POST","/conversations/"+id+"/messages/"+message.path("id").asText()+"/retry",Map.of("clientRequestId",UUID.randomUUID().toString()),200);
                } else return value;
            }
            Thread.sleep(50);
        }
        fail("生成未按时结束"); return null;
    }

    @Test void actualStreamHasIncrementBeforeCompletionAndReconnectDoesNotGenerateAgain() throws Exception {
        String token=account(), id=conversation(token);
        String task=send(token,id,"进程与线程","stream").path("taskId").asText();
        var response=HTTP.send(request(token,"/conversations/"+id+"/generations/"+task+"/stream").GET().build(),HttpResponse.BodyHandlers.ofInputStream());
        assertEquals(200,response.statusCode());
        boolean delta=false, completed=false;
        try(var reader=new BufferedReader(new InputStreamReader(response.body()))) {
            String line;
            while((line=reader.readLine())!=null) {
                if(line.equals("event:delta")) {
                    if(!delta) assertEquals("RUNNING",latest(token,id).path("status").asText());
                    delta=true;
                }
                if(line.equals("event:completed")) completed=true;
            }
        }
        assertTrue(delta,"结束前必须收到真实SDK流增量"); assertTrue(completed);
        var saved=finish(token,id);
        assertEquals("SUCCESS",saved.path("status").asText());
        assertEquals("线程共享地址空间，保留各自的栈。",saved.path("result").path("answer").asText());
        var reconnect=HTTP.send(request(token,"/conversations/"+id+"/generations/"+task+"/stream").GET().build(),HttpResponse.BodyHandlers.ofString());
        assertTrue(reconnect.body().contains("snapshot")); assertTrue(reconnect.body().contains("SUCCESS"));
        assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM chat_generation WHERE conversation_id=?",Integer.class,id));
        var second=send(token,id,"它们共享哪些资源","followup");
        assertNotEquals(task,second.path("taskId").asText());
        assertEquals("它们共享哪些资源",finish(token,id).path("result").path("standaloneQuery").asText(),"展开的历史检索词不另存为新副本");
    }

    @Test void newSourceHostsPersistThroughChatAndSynchronousHttp() throws Exception {
        for (String mode : List.of("github", "mit", "school")) {
            String token=privateAccount(), id=conversation(token);
            String task=send(token,id,"source-policy-fixture:"+mode,"allowed-host").path("taskId").asText();
            var saved=finish(token,id);
            assertEquals("SUCCESS",saved.path("status").asText(),saved.toString());
            assertEquals("SUCCESS",jdbc.queryForObject("SELECT status FROM task WHERE id=?",String.class,task));
            assertTrue(saved.path("result").path("references").get(0).path("url").asText().startsWith("https://"));
            var sync=call(token,"POST","/tasks",Map.of("taskType","KNOWLEDGE_QA",
                "input",Map.of("query","source-policy-fixture:"+mode)),200);
            assertEquals("SUCCESS",sync.path("status").asText(),sync.toString());
            assertEquals(saved.path("result").path("references"),sync.path("resultPayload").path("references"));
        }
    }

    @Test void heapSortTopicCommandsPreviewThenConfirmWithoutPublicReferences() throws Exception {
        for (String prefix : List.of("有关", "涉及")) {
            String token=privateAccount(),id=conversation(token);
            long owner=call(token,"GET","/users/me",null,200).path("id").asLong(),base=9000000+owner*10;
            for (int i=0;i<2;i++) {
                jdbc.update("INSERT INTO question(id,subject,knowledge_point,content,option_a,option_b,option_c,option_d,answer,analysis,difficulty,question_type,version,active,stable_order,review_status) VALUES(?,'数据结构',?,'合成题目','甲','乙','丙','丁','A','不得泄露的合成解析','EASY','SINGLE_CHOICE',1,1,1,'APPROVED')",base+i,i==0?"堆排序":"队列");
                jdbc.update("INSERT INTO user_question_mark(user_id,question_id,is_favorite,is_wrong,wrong_count) VALUES(?,?,0,1,1)",owner,base+i);
            }
            send(token,id,"将我的错题本中"+prefix+"堆排序的题目加入收藏","heap-sort-command");
            var saved=finish(token,id);
            assertEquals("SUCCESS",saved.path("status").asText(),saved.toString());
            var result=saved.path("result");var action=result.path("actions").get(0);
            assertNotNull(action,result.toString());assertEquals("PENDING",action.path("status").asText());
            assertEquals(1,action.path("count").asInt());
            assertEquals(base,action.path("targets").get(0).path("resource").path("id").asLong());
            assertTrue(result.path("references").isEmpty());
            assertFalse(result.path("answer").asText().contains("相关审核资料"));
            assertEquals(0,jdbc.queryForObject("SELECT SUM(is_favorite) FROM user_question_mark WHERE user_id=?",Integer.class,owner));
            var confirmed=call(token,"POST","/conversations/"+id+"/actions/"+action.path("id").asText()+"/confirm",null,200);
            assertEquals("SUCCESS",confirmed.path("status").asText());
            assertEquals(1,jdbc.queryForObject("SELECT is_favorite FROM user_question_mark WHERE user_id=? AND question_id=?",Integer.class,owner,base));
            assertEquals(0,jdbc.queryForObject("SELECT is_favorite FROM user_question_mark WHERE user_id=? AND question_id=?",Integer.class,owner,base+1));
        }
    }

    @Test void rejectedUpstreamResultsLogFixedCodesAndPersistSanitizedFailures(CapturedOutput output) throws Exception {
        var cases=Map.of("denied","SOURCE_HOST_NOT_ALLOWED","plan","PLAN_VALIDATION_FAILED",
            "result","RESULT_VALIDATION_FAILED","conditions","CONDITIONS_VALIDATION_FAILED",
            "document","DOCUMENT_VALIDATION_FAILED","upstream","UPSTREAM_FAILED");
        for (var entry:cases.entrySet()) {
            String token=privateAccount(),id=conversation(token);
            String task=send(token,id,"source-policy-fixture:"+entry.getKey(),"rejected").path("taskId").asText();
            var saved=finish(token,id);
            assertEquals("FAILED",saved.path("status").asText(),saved.toString());
            assertEquals("生成失败或输出未通过校验，请重试",saved.path("errorMessage").asText());
            assertEquals("FAILED",jdbc.queryForObject("SELECT status FROM task WHERE id=?",String.class,task));
            assertTrue(output.getAll().lines().anyMatch(line -> line.contains("task="+task)
                && line.contains("errorCode="+entry.getValue())),output.getAll());
            assertFalse(saved.toString().contains("PRIVATE_"));
        }
        assertFalse(output.getAll().contains("PRIVATE_"));
        String token=privateAccount();
        var sync=call(token,"POST","/tasks",Map.of("taskType","KNOWLEDGE_QA",
            "input",Map.of("query","source-policy-fixture:denied")),200);
        assertEquals("FAILED",sync.path("status").asText());
    }

    @Test void duplicateRequestsConcurrencyCancellationRetryAndOwnership() throws Exception {
        String token=account(), other=account(), id=conversation(token);
        var first=send(token,id,"进程与线程，等待停止","same");
        String task=first.path("taskId").asText(), message=first.path("messageId").asText();
        assertEquals(task,send(token,id,"进程与线程，等待停止","same").path("taskId").asText());
        call(token,"POST","/conversations/"+id+"/messages",Map.of("query","不同内容","clientRequestId","same"),409);
        call(token,"POST","/conversations/"+id+"/messages",Map.of("query","第二标签页","clientRequestId","another"),409);
        call(other,"GET","/conversations/"+id+"/messages",null,404);
        call(other,"GET","/conversations/"+id+"/generations/"+task+"/stream",null,404);
        call(other,"POST","/conversations/"+id+"/generations/"+task+"/cancel",null,404);
        call(other,"POST","/conversations/"+id+"/messages/"+message+"/retry",Map.of("clientRequestId","other"),404);
        call(token,"POST","/conversations/"+id+"/generations/"+task+"/cancel",null,200);
        assertEquals("CANCELLED",latest(token,id).path("status").asText());
        var retry=call(token,"POST","/conversations/"+id+"/messages/"+message+"/retry",Map.of("clientRequestId","retry"),200);
        assertNotEquals(task,retry.path("taskId").asText());
        assertEquals(retry.path("taskId"),call(token,"POST","/conversations/"+id+"/messages/"+message+"/retry",Map.of("clientRequestId","retry"),200).path("taskId"));
        call(token,"POST","/conversations/"+id+"/generations/"+retry.path("taskId").asText()+"/cancel",null,200);
        send(token,id,"进程与线程","new-question"); finish(token,id);
        call(token,"POST","/conversations/"+id+"/messages/"+message+"/retry",Map.of("clientRequestId","old-retry"),409);
        assertEquals(3,jdbc.queryForObject("SELECT COUNT(*) FROM task WHERE id IN (SELECT task_id FROM chat_generation WHERE conversation_id=?)",Integer.class,id));
    }

    @Test void simultaneousTabsWithIdenticalRequestReserveExactlyOneTask() throws Exception {
        String token=account(),id=conversation(token);
        var pool=Executors.newFixedThreadPool(2);
        var gate=new CountDownLatch(1);
        Callable<JsonNode> submit=() -> { gate.await(); return send(token,id,"进程与线程，等待停止","concurrent-request"); };
        try {
            var first=pool.submit(submit); var second=pool.submit(submit); gate.countDown();
            var a=first.get(5,TimeUnit.SECONDS); var b=second.get(5,TimeUnit.SECONDS);
            assertEquals(a.path("taskId"),b.path("taskId"));
            assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM chat_generation WHERE conversation_id=?",Integer.class,id));
            assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM chat_message WHERE conversation_id=?",Integer.class,id));
            call(token,"POST","/conversations/"+id+"/generations/"+a.path("taskId").asText()+"/cancel",null,200);
        } finally { pool.shutdownNow(); }
    }

    @Test void documentProposalNeedsConfirmationIsIdempotentAndDetectsConflictingVersions() throws Exception {
        String token=account(), other=account(), id=conversation(token);
        String task=send(token,id,"创建线程学习笔记","create").path("taskId").asText();
        var result=finish(token,id);
        assertEquals("SUCCESS",result.path("status").asText());
        assertTrue(result.path("result").has("documentProposal"));
        assertEquals(0,call(token,"GET","/personal-documents",null,200).path("total").asInt());
        var document=call(token,"POST","/conversations/"+id+"/generations/"+task+"/apply-document",null,200);
        String docId=document.path("id").asText(); assertEquals(1,document.path("version").asInt());
        assertEquals(docId,call(token,"POST","/conversations/"+id+"/generations/"+task+"/apply-document",null,200).path("id").asText());
        call(other,"GET","/personal-documents/"+docId,null,404);
        call(other,"PUT","/personal-documents/"+docId,Map.of("title","盗改","content","x","baseVersion",1),404);
        call(other,"POST","/conversations/"+id+"/generations/"+task+"/apply-document",null,404);
        var update=call(token,"POST","/conversations/"+id+"/messages",Map.of("query","修改文档补充线程说明","clientRequestId","update","documentId",docId,"documentVersion",1),200);
        assertEquals("SUCCESS",finish(token,id).path("status").asText());
        call(token,"PUT","/personal-documents/"+docId,Map.of("title","人工修订","content","保留人工内容","baseVersion",1),200);
        call(token,"POST","/conversations/"+id+"/generations/"+update.path("taskId").asText()+"/apply-document",null,409);
        assertEquals("保留人工内容",call(token,"GET","/personal-documents/"+docId,null,200).path("content").asText());
        assertEquals(2,call(token,"GET","/personal-documents/"+docId+"/versions",null,200).path("total").asInt());
        // Replaying the earlier confirmed proposal cannot overwrite the newer manual version.
        call(token,"POST","/conversations/"+id+"/generations/"+task+"/apply-document",null,200);
        assertEquals(2,call(token,"GET","/personal-documents/"+docId,null,200).path("version").asInt());
    }

    @Test void invalidCitationFallsBackAndRestartRecoveryClearsDraftAndActiveLock() throws Exception {
        String token=account(), id=conversation(token);
        send(token,id,"进程与线程，非法引用","bad-source");
        var result=finish(token,id);
        assertEquals("fallback",result.path("result").path("explanationMode").asText());
        assertTrue(result.path("draft").isEmpty());
        // Simulate persisted interrupted work without touching a live provider call.
        String task=UUID.randomUUID().toString();
        jdbc.update("INSERT INTO chat_generation(task_id,conversation_id,message_id,user_id,attempt_no,client_request_id,request_hash,status,active_conversation_id,context_json,draft_json) VALUES(?,?,?,1,1,'restart','hash','RUNNING',?,'{}','{\"answer\":\"临时\"}')",task,id,"interrupted",id);
        service.recover();
        assertEquals("FAILED",jdbc.queryForObject("SELECT status FROM chat_generation WHERE task_id=?",String.class,task));
        assertNull(jdbc.queryForObject("SELECT active_conversation_id FROM chat_generation WHERE task_id=?",String.class,task));
    }

    @Test void privacyDefaultsOffAndClearPurgesEveryChatCopyButPreservesNotesAndQuota() throws Exception {
        String token=privateAccount(),other=privateAccount(),id=conversation(token);
        var settings=call(token,"GET","/privacy/settings",null,200);
        assertFalse(settings.path("modelAllowed").asBoolean());assertTrue(settings.path("scopes").isEmpty());
        assertEquals(30,settings.path("retentionDays").asInt());
        String note=call(token,"POST","/personal-documents",Map.of("title","保留的笔记","content","SYNTHETIC_NOTE_MARKER"),200).path("id").asText();
        String task=send(token,id,"进程与线程 SYNTHETIC_CHAT_MARKER","private-request").path("taskId").asText();
        var output=finish(token,id);
        assertEquals("SUCCESS",output.path("status").asText());
        assertEquals("rules",output.path("result").path("explanationMode").asText());
        assertFalse(call(token,"GET","/tasks/"+task,null,200).has("inputPayload"));
        assertFalse(jdbc.queryForObject("SELECT input_payload FROM task WHERE id=?",String.class,task).contains("SYNTHETIC_CHAT_MARKER"));
        call(other,"DELETE","/conversations/"+id,null,404);
        call(token,"DELETE","/conversations/"+id,null,200);
        call(token,"GET","/conversations/"+id+"/messages",null,404);
        assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM chat_generation WHERE task_id=?",Integer.class,task));
        var saved=jdbc.queryForMap("SELECT input_payload,result_payload,error_message FROM task WHERE id=?",task);
        assertTrue(saved.values().stream().allMatch(Objects::isNull));
        assertEquals("SYNTHETIC_NOTE_MARKER",call(token,"GET","/personal-documents/"+note,null,200).path("content").asText());
        assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM task WHERE id=?",Integer.class,task),"额度记录仍存在");
    }

    @Test void expiryIsEnforcedOnReadAndPrivacyWithdrawalCancelsInFlightGeneration() throws Exception {
        String token=account(),id=conversation(token);
        String task=send(token,id,"进程与线程，等待停止","withdraw").path("taskId").asText();
        var settings=call(token,"GET","/privacy/settings",null,200);
        call(token,"PUT","/privacy/settings",Map.of("modelAllowed",false,"scopes",List.of(),"provider",settings.path("provider").asText()),200);
        assertEquals("CANCELLED",latest(token,id).path("status").asText());
        jdbc.update("UPDATE chat_message SET created_at=DATEADD('DAY',-31,CURRENT_TIMESTAMP) WHERE conversation_id=?",id);
        call(token,"GET","/tasks/"+task,null,404);
        assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM chat_generation WHERE task_id=?",Integer.class,task));
        assertNull(jdbc.queryForObject("SELECT result_payload FROM task WHERE id=?",String.class,task));
    }

    @Test void localFavoriteAndConfirmedPracticeSurviveRefreshWithoutSendingPrivateDataToModel() throws Exception {
        String token=privateAccount(),id=conversation(token);
        Long owner=call(token,"GET","/users/me",null,200).path("id").asLong();
        long question=900000+owner;
        jdbc.update("INSERT INTO question(id,subject,knowledge_point,content,option_a,option_b,option_c,option_d,answer,analysis,difficulty,question_type,version,active,stable_order,review_status) VALUES(?, '操作系统','线程','合成测试题','甲','乙','丙','丁','A','合成解析','EASY','SINGLE_CHOICE',1,1,1,'APPROVED')",question);
        jdbc.update("INSERT INTO user_question_mark(user_id,question_id,is_favorite,is_wrong,wrong_count) VALUES(?,?,0,1,1)",owner,question);
        var page=Map.of("page","wrong","selectedQuestionIds",List.of(question),"visibleQuestionIds",List.of(question));
        call(token,"POST","/conversations/"+id+"/messages",Map.of("query","帮我收藏这道题","clientRequestId","favorite","pageContext",page),200);
        var result=finish(token,id);
        assertEquals("SUCCESS",result.path("status").asText(),result.toString());
        assertEquals("SUCCESS",result.path("result").path("actions").get(0).path("status").asText());
        assertEquals(1,jdbc.queryForObject("SELECT is_favorite FROM user_question_mark WHERE user_id=? AND question_id=?",Integer.class,owner,question));
        assertFalse(result.path("result").path("answer").asText().contains("合成解析"),"未答题答案与解析保持隐藏");
        call(token,"POST","/conversations/"+id+"/messages",Map.of("query","从我的错题安排5道练习","clientRequestId","practice","pageContext",page),200);
        var proposal=finish(token,id);assertEquals("SUCCESS",proposal.path("status").asText(),proposal.toString());
        String action=proposal.path("result").path("actions").get(0).path("id").asText();
        assertEquals("PENDING",proposal.path("result").path("actions").get(0).path("status").asText());
        assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM practice_record WHERE user_id=?",Integer.class,owner));
        var confirmed=call(token,"POST","/conversations/"+id+"/actions/"+action+"/confirm",null,200);
        assertEquals("SUCCESS",confirmed.path("status").asText());
        String session=confirmed.path("result").path("sessionId").asText();
        assertEquals(session,call(token,"POST","/conversations/"+id+"/actions/"+action+"/confirm",null,200).path("result").path("sessionId").asText());
        assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM practice_record WHERE user_id=?",Integer.class,owner));
        assertEquals("SUCCESS",latest(token,id).path("result").path("actions").get(0).path("status").asText());
    }

    @Test void derivedHistoryKeepsPrivacyCategoriesAndOldProseIsNotCopiedIntoNewSnapshots() throws Exception {
        String token=account(),id=conversation(token);
        send(token,id,"分析我的收藏","scoped-history");
        assertTrue(finish(token,id).path("result").path("dataScopes").toString().contains("favorite"));
        String second=send(token,id,"进程与线程","derived-history").path("taskId").asText();
        assertTrue(finish(token,id).path("result").path("dataScopes").toString().contains("favorite"));
        String stored=jdbc.queryForObject("SELECT context_json FROM chat_generation WHERE task_id=?",String.class,second);
        assertFalse(stored.contains("分析我的收藏"),"历史正文只按引用读取，不延长原文保存期限");
        var settings=call(token,"GET","/privacy/settings",null,200);
        call(token,"PUT","/privacy/settings",Map.of("modelAllowed",true,"scopes",java.util.List.of("profile","document"),"provider",settings.path("provider").asText()),200);
        String third=send(token,id,"进程与线程","withdrawn-history").path("taskId").asText();
        assertEquals("SUCCESS",finish(token,id).path("status").asText());
        var fresh=json.readTree(jdbc.queryForObject("SELECT context_json FROM chat_generation WHERE task_id=?",String.class,third));
        assertTrue(fresh.path("_historyRefs").isEmpty(),"撤回类别后不得转发其派生历史");
    }

    @Test void heapFollowupAndExplicitAnswerReferenceNeverRebindQ1ToNewFavoriteList() throws Exception {
        String token=privateAccount(),id=conversation(token);
        long owner=call(token,"GET","/users/me",null,200).path("id").asLong(),heap=2000000+owner*10,noise=heap+1;
        for(long q:List.of(heap,noise)) {
            jdbc.update("INSERT INTO question(id,subject,knowledge_point,content,option_a,option_b,option_c,option_d,answer,analysis,difficulty,question_type,version,active,stable_order,review_status) VALUES(?,'数据结构',?,'合成题目','甲','乙','丙','丁','A','合成解析','EASY','SINGLE_CHOICE',1,1,1,'APPROVED')",q,q==heap?"堆":"AVL树");
            jdbc.update("INSERT INTO user_question_mark(user_id,question_id,is_favorite,is_wrong,wrong_count) VALUES(?,?,?,1,1)",owner,q,q==noise?1:0);
        }
        String source=send(token,id,"把错题中跟堆有关的错题整理给我","heap-read").path("taskId").asText();
        var read=finish(token,id);assertEquals("SUCCESS",read.path("status").asText(),read.toString());
        source=read.path("taskId").asText();
        assertEquals(1,read.path("result").path("evidence").size());
        assertEquals(heap,read.path("result").path("evidence").get(0).path("resource").path("id").asLong());
        send(token,id,"将其加入我的收藏","heap-pronoun");
        assertEquals("SUCCESS",finish(token,id).path("result").path("actions").get(0).path("status").asText());
        jdbc.update("UPDATE user_question_mark SET is_favorite=0 WHERE user_id=? AND question_id=?",owner,heap);
        send(token,id,"分析我的收藏","other-list");finish(token,id);
        call(token,"POST","/conversations/"+id+"/messages",Map.of("query","收藏 Q1","clientRequestId","bound-reference","referenceTaskId",source,
            "pageContext",Map.of("page","practice","selectedQuestionIds",List.of(noise),"visibleQuestionIds",List.of(noise))),200);
        var saved=finish(token,id);
        assertEquals("SUCCESS",saved.path("status").asText(),saved.toString());
        assertEquals(heap,saved.path("result").path("actions").get(0).path("targets").get(0).path("resource").path("id").asLong());
        assertEquals(1,jdbc.queryForObject("SELECT is_favorite FROM user_question_mark WHERE user_id=? AND question_id=?",Integer.class,owner,heap));
        assertTrue(saved.path("result").path("answer").asText().contains("已加入收藏"));
        String otherConversation=conversation(token);
        call(token,"POST","/conversations/"+otherConversation+"/messages",Map.of("query","收藏 Q1","clientRequestId","wrong-conversation","referenceTaskId",source),404);
        String other=privateAccount(),foreignConversation=conversation(other);
        call(other,"POST","/conversations/"+foreignConversation+"/messages",Map.of("query","收藏 Q1","clientRequestId","foreign-reference","referenceTaskId",source),404);
        send(token,id,"你帮我查看一下题号，并将其加入我的收藏","composite-command");
        assertEquals("SUCCESS",finish(token,id).path("result").path("actions").get(0).path("status").asText());
    }

    @Test void tcpCollectionCommandUsesCurrentWrongBookAndClarificationOffersRecommendedQuestions() throws Exception {
        String token=privateAccount(),id=conversation(token);
        long owner=call(token,"GET","/users/me",null,200).path("id").asLong(),base=4000000+owner*100;
        for(int i=0;i<18;i++) {
            String point=i==0?"TCP拥塞控制":i==1?"TCP序号":i==17?"TCP可靠传输":"路由选择";
            jdbc.update("INSERT INTO question(id,subject,knowledge_point,content,option_a,option_b,option_c,option_d,answer,analysis,difficulty,question_type,version,active,stable_order,review_status) VALUES(?,'计算机网络',?,'合成题目','甲','乙','丙','丁','A','合成解析','EASY','SINGLE_CHOICE',1,1,1,'APPROVED')",base+i,point);
            jdbc.update("INSERT INTO user_question_mark(user_id,question_id,is_favorite,is_wrong,wrong_count) VALUES(?,?,?,?,1)",owner,base+i,i==17?1:0,i==17?0:1);
        }
        // A broad prior result and an unrelated page selection must not capture a fresh collection command.
        send(token,id,"分析我的错题","tcp-prior");finish(token,id);
        call(token,"POST","/conversations/"+id+"/messages",Map.of("query","将我错题本中涉及tcp协议内容的部分加入我的收藏","clientRequestId","tcp-collection",
            "pageContext",Map.of("page","favorite","subject","数据结构","selectedQuestionIds",List.of(base+17),"visibleQuestionIds",List.of(base+17))),200);
        var saved=finish(token,id);assertEquals("SUCCESS",saved.path("status").asText(),saved.toString());
        var action=saved.path("result").path("actions").get(0);
        assertNotNull(action,saved.toString());assertEquals("PENDING",action.path("status").asText());assertEquals(2,action.path("count").asInt());
        Set<Long> targets=new HashSet<>();action.path("targets").forEach(t->targets.add(t.path("resource").path("id").asLong()));
        assertEquals(Set.of(base,base+1),targets);
        assertEquals(0,jdbc.queryForObject("SELECT SUM(is_favorite) FROM user_question_mark WHERE user_id=? AND is_wrong=1",Integer.class,owner));
        call(token,"POST","/conversations/"+id+"/actions/"+action.path("id").asText()+"/confirm",null,200);
        call(token,"POST","/conversations/"+id+"/actions/"+action.path("id").asText()+"/confirm",null,200);
        assertEquals(2,jdbc.queryForObject("SELECT SUM(is_favorite) FROM user_question_mark WHERE user_id=? AND is_wrong=1",Integer.class,owner));
        send(token,id,"将错题本中涉及未知主题的题加入收藏","tcp-unknown");
        var unclear=finish(token,id).path("result");assertEquals("NEEDS_INPUT",unclear.path("outcome").asText());
        assertTrue(unclear.path("answer").asText().contains("推荐问法"));assertTrue(unclear.path("actions").isEmpty());
        send(token,id,"将错题本中涉及 UDP 的题加入收藏","tcp-zero");
        var empty=finish(token,id).path("result");assertEquals("NEEDS_INPUT",empty.path("outcome").asText());
        assertTrue(empty.path("answer").asText().contains("推荐问法"));assertTrue(empty.path("actions").isEmpty());
        String fresh=conversation(token);
        send(token,fresh,"帮我收藏","missing-target");
        var missing=finish(token,fresh).path("result");assertEquals("NEEDS_INPUT",missing.path("outcome").asText());
        assertTrue(missing.path("answer").asText().contains("推荐问法"));assertTrue(missing.path("actions").isEmpty());
    }

    @Test void publicMaterialSelectedUsingWithdrawnPrivateTopicDoesNotReachModel() throws Exception {
        String token=account(),id=conversation(token);long owner=call(token,"GET","/users/me",null,200).path("id").asLong(),question=3000000+owner;
        jdbc.update("INSERT INTO question(id,subject,knowledge_point,content,option_a,option_b,option_c,option_d,answer,analysis,difficulty,question_type,version,active,stable_order,review_status) VALUES(?,'数据结构','堆','合成堆题','甲','乙','丙','丁','A','解析','EASY','SINGLE_CHOICE',1,1,1,'APPROVED')",question);
        jdbc.update("INSERT INTO user_question_mark(user_id,question_id,is_favorite,is_wrong,wrong_count) VALUES(?,?,0,1,1)",owner,question);
        jdbc.update("INSERT INTO document(id,subject,title,content,status) VALUES(?,'数据结构','合成堆资料','堆主题的公开测试摘要','PUBLISHED')",question);
        send(token,id,"把错题中跟堆有关的错题整理给我","private-topic");String source=finish(token,id).path("taskId").asText();
        var settings=call(token,"GET","/privacy/settings",null,200);
        call(token,"PUT","/privacy/settings",Map.of("modelAllowed",true,"scopes",List.of("document"),"provider",settings.path("provider").asText()),200);
        call(token,"POST","/conversations/"+id+"/messages",Map.of("query","推荐相关复习资料","clientRequestId","derived-public-material","referenceTaskId",source),200);
        var result=finish(token,id);
        assertEquals("SUCCESS",result.path("status").asText(),result.toString());
        assertEquals("rules",result.path("result").path("explanationMode").asText(),"不能通过公开资料间接外发已撤回的私人主题");
        assertTrue(result.path("result").path("dataScopes").toString().contains("wrong"));
        assertEquals(question,result.path("result").path("evidence").get(0).path("resource").path("id").asLong());
    }
    @Test void semanticWrongFavoriteAndPublishedPracticeUseAuthorizedMatches() throws Exception {
        String token=privateAccount(),id=conversation(token);long owner=call(token,"GET","/users/me",null,200).path("id").asLong(),base=8000000+owner*10;
        for(int i=0;i<4;i++) {
            String point=i==0?"二叉树":i==1?"遍历":"队列";
            String content=i==1?"左右孩子的访问顺序":"合成题目";
            jdbc.update("INSERT INTO question(id,subject,knowledge_point,content,option_a,option_b,option_c,option_d,answer,analysis,difficulty,question_type,version,active,stable_order,review_status) VALUES(?,'数据结构',?,?,'甲','乙','丙','丁','A','不得用于检索的解析','EASY','SINGLE_CHOICE',1,1,1,'APPROVED')",base+i,point,content);
            jdbc.update("INSERT INTO user_question_mark(user_id,question_id,is_favorite,is_wrong,wrong_count) VALUES(?,?,0,1,1)",i==3?owner+999999:owner,base+i);
        }
        send(token,id,"将我的错题本中涉及二叉树的题目加入收藏","binary-wrong");
        var result=finish(token,id).path("result");var action=result.path("actions").get(0);
        assertNotNull(action,result.toString());assertEquals("PENDING",action.path("status").asText());assertEquals(2,action.path("count").asInt());
        Set<String> methods=new HashSet<>();action.path("targets").forEach(t->methods.add(t.path("matchMethod").asText()));assertEquals(Set.of("LABEL","SEMANTIC"),methods);
        assertFalse(result.toString().contains("不得用于检索的解析"));
        assertEquals(0,jdbc.queryForObject("SELECT SUM(is_favorite) FROM user_question_mark WHERE user_id=?",Integer.class,owner));
        call(token,"POST","/conversations/"+id+"/actions/"+action.path("id").asText()+"/confirm",null,200);
        call(token,"POST","/conversations/"+id+"/actions/"+action.path("id").asText()+"/confirm",null,200);
        send(token,id,"在我的收藏夹中查找涉及二叉树的题目","binary-favorites");
        assertEquals(2,finish(token,id).path("result").path("evidence").size());
        // New conversation avoids mixing older aliases into a public collection request.
        id=conversation(token);
        send(token,id,"从全题库创建5道关于二叉树的题目练习","binary-practice");
        result=finish(token,id).path("result");action=result.path("actions").get(0);
        assertNotNull(action,result.toString());assertEquals(2,action.path("count").asInt());assertEquals(5,action.path("requestedCount").asInt());
        var confirmed=call(token,"POST","/conversations/"+id+"/actions/"+action.path("id").asText()+"/confirm",null,200);
        assertEquals(2,confirmed.path("result").path("actualCount").asInt());
        assertEquals(2,jdbc.queryForObject("SELECT COUNT(*) FROM practice_record WHERE user_id=? AND session_id=?",Integer.class,owner,confirmed.path("result").path("sessionId").asText()));
    }

}
