package course.kaoyan;

import com.fasterxml.jackson.databind.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties={"spring.datasource.url=jdbc:h2:mem:practice-tests;MODE=PostgreSQL;DB_CLOSE_DELAY=-1",
    "spring.jpa.hibernate.ddl-auto=create-drop", "agent.internal-key=test-internal-key-123456789"})
@AutoConfigureMockMvc
class PracticeTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;

    private JsonNode register() throws Exception {
        String name = "p" + UUID.randomUUID().toString().replace("-", "").substring(0,20);
        return mapper.readTree(mvc.perform(post("/api/auth/register").contentType("application/json")
            .content(mapper.writeValueAsString(Map.of("username", name, "password", "test-password"))))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
    }
    private String token(JsonNode login) { return login.path("token").asText(); }
    private JsonNode create(String token, String mode) throws Exception {
        return mapper.readTree(mvc.perform(post("/api/practice-sessions").header("Authorization", "Bearer " + token)
            .contentType("application/json").content("{\"mode\":\""+mode+"\",\"subject\":\"data_structure\",\"questionCount\":1}"))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
    }
    private JsonNode item(String token, JsonNode session) throws Exception {
        String itemId = session.path("items").get(0).path("id").asText();
        return mapper.readTree(mvc.perform(get("/api/practice-sessions/"+session.path("id").asText()+"/items/"+itemId)
            .header("Authorization", "Bearer " + token)).andExpect(status().isOk())
            .andReturn().getResponse().getContentAsString());
    }
    private JsonNode submit(String token, JsonNode session, JsonNode item, String option, UUID requestId) throws Exception {
        Map<String,Object> body = new LinkedHashMap<>();
        body.put("questionId", item.path("questionId").asText());
        body.put("questionVersionId", item.path("questionVersionId").asText());
        body.put("selectedOption", option); body.put("clientRequestId", requestId);
        body.put("sessionId", session.path("id").asText()); body.put("sessionItemId", item.path("id").asText());
        return mapper.readTree(mvc.perform(post("/api/attempts").header("Authorization", "Bearer " + token)
            .contentType("application/json").content(mapper.writeValueAsString(body)))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
    }

    @Test void questionCatalogHidesAnswersAndSupportsFilters() throws Exception {
        String token = token(register());
        mvc.perform(get("/api/questions?subject=operating_system&difficulty=easy").header("Authorization","Bearer "+token))
            .andExpect(status().isOk()).andExpect(jsonPath("$.totalItems").value(1))
            .andExpect(jsonPath("$.items[0].stem").exists()).andExpect(jsonPath("$.items[0].correctOption").doesNotExist())
            .andExpect(jsonPath("$.items[0].explanation").doesNotExist());
        mvc.perform(get("/api/knowledge/points?subject=data_structure").header("Authorization","Bearer "+token))
            .andExpect(status().isOk()).andExpect(jsonPath("$[0].name").exists());
    }

    @Test void sessionDraftUsesRevisionAndIsAccountIsolated() throws Exception {
        var first=register(); var second=register(); JsonNode session=create(token(first),"chapter"); JsonNode item=item(token(first),session);
        Map<String,Object> progress=Map.of("expectedRevision",session.path("revision").asLong(),"currentOrdinal",1,
            "drafts",List.of(Map.of("itemId",item.path("id").asText(),"selectedOption","A")));
        mvc.perform(put("/api/practice-sessions/"+session.path("id").asText()+"/progress").header("Authorization","Bearer "+token(first))
            .contentType("application/json").content(mapper.writeValueAsString(progress)))
            .andExpect(status().isOk()).andExpect(jsonPath("$.revision").value(1));
        mvc.perform(put("/api/practice-sessions/"+session.path("id").asText()+"/progress").header("Authorization","Bearer "+token(first))
            .contentType("application/json").content(mapper.writeValueAsString(progress)))
            .andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("STALE_REVISION"));
        mvc.perform(get("/api/practice-sessions/"+session.path("id").asText()).header("Authorization","Bearer "+token(second)))
            .andExpect(status().isNotFound());
    }

    @Test void hintsMustBeOrderedAndAssistedCorrectDoesNotMasterWrongQuestion() throws Exception {
        String token=token(register()); JsonNode first=create(token,"chapter"); JsonNode firstItem=item(token,first);
        submit(token,first,firstItem,"A",UUID.randomUUID());
        JsonNode second=create(token,"chapter"); JsonNode secondItem=item(token,second);
        String hintPath="/api/practice-sessions/"+second.path("id").asText()+"/items/"+secondItem.path("id").asText()+"/hints";
        mvc.perform(post(hintPath).header("Authorization","Bearer "+token).contentType("application/json").content("{\"level\":2}"))
            .andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("HINT_ORDER"));
        mvc.perform(post(hintPath).header("Authorization","Bearer "+token).contentType("application/json").content("{\"level\":1}"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.available").value(true));
        submit(token,second,secondItem,"B",UUID.randomUUID());
        mvc.perform(get("/api/wrong-questions?status=reviewing").header("Authorization","Bearer "+token))
            .andExpect(status().isOk()).andExpect(jsonPath("$.items[0].consecutiveCorrect").value(0));
    }

    @Test void replayIsIdempotentAndConflictingReplayIsRejected() throws Exception {
        String token=token(register()); JsonNode session=create(token,"chapter"); JsonNode item=item(token,session); UUID request=UUID.randomUUID();
        JsonNode first=submit(token,session,item,"A",request);
        JsonNode replay=submit(token,session,item,"A",request); assertEquals(first.path("id").asText(),replay.path("id").asText());
        Map<String,Object> conflict=Map.of("questionId",item.path("questionId").asText(),"questionVersionId",item.path("questionVersionId").asText(),
            "selectedOption","B","clientRequestId",request,"sessionId",session.path("id").asText(),"sessionItemId",item.path("id").asText());
        mvc.perform(post("/api/attempts").header("Authorization","Bearer "+token).contentType("application/json")
            .content(mapper.writeValueAsString(conflict))).andExpect(status().isConflict())
            .andExpect(jsonPath("$.code").value("REQUEST_CONFLICT"));
    }

    @Test void twoIndependentCorrectRetriesMarkWrongQuestionMastered() throws Exception {
        String token=token(register()); JsonNode first=create(token,"chapter"); submit(token,first,item(token,first),"A",UUID.randomUUID());
        for(int i=0;i<2;i++){JsonNode next=create(token,"chapter"); submit(token,next,item(token,next),"B",UUID.randomUUID());}
        mvc.perform(get("/api/wrong-questions?status=mastered").header("Authorization","Bearer "+token))
            .andExpect(status().isOk()).andExpect(jsonPath("$.totalItems").value(1))
            .andExpect(jsonPath("$.items[0].consecutiveCorrect").value(2));
    }

    @Test void favoritesAndWrongPoolsCreateRealSessions() throws Exception {
        String token=token(register()); JsonNode base=create(token,"chapter"); JsonNode baseItem=item(token,base);
        String questionId=baseItem.path("questionId").asText();
        mvc.perform(put("/api/favorites/"+questionId).header("Authorization","Bearer "+token)).andExpect(status().isOk());
        create(token,"favorite"); submit(token,base,baseItem,"A",UUID.randomUUID());
        JsonNode wrong=create(token,"wrong"); assertEquals(1,wrong.path("actualCount").asInt());
        mvc.perform(get("/api/favorites").header("Authorization","Bearer "+token)).andExpect(jsonPath("$.totalItems").value(1));
    }

    @Test void completedSessionAndStudySummaryUsePersistedAttempts() throws Exception {
        String token=token(register()); JsonNode session=create(token,"chapter"); JsonNode answer=submit(token,session,item(token,session),"B",UUID.randomUUID());
        assertTrue(answer.path("correct").asBoolean());
        mvc.perform(get("/api/practice-sessions/"+session.path("id").asText()+"/result").header("Authorization","Bearer "+token))
            .andExpect(status().isOk()).andExpect(jsonPath("$.answered").value(1)).andExpect(jsonPath("$.accuracy").value(1.0));
        mvc.perform(get("/api/study/summary").header("Authorization","Bearer "+token))
            .andExpect(status().isOk()).andExpect(jsonPath("$.validAttempts").value(1))
            .andExpect(jsonPath("$.uniqueQuestions").value(1)).andExpect(jsonPath("$.knowledgePoints[0].attempts").value(1));
    }
}
