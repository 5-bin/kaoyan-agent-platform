package course.kaoyan.task;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import org.springframework.http.MediaType;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class AgentClientTest {
    private static final String ID="12345678-1234-1234-1234-123456789012";
    @Test void serializesContractAndChecksTaskId() {
        var builder=RestClient.builder().baseUrl("http://agent.test").defaultHeader("X-Internal-Key","test-key");
        var server=MockRestServiceServer.bindTo(builder).build(); var client=new AgentClient(builder.build());
        server.expect(requestTo("http://agent.test/internal/run")).andExpect(header("X-Internal-Key","test-key"))
            .andExpect(content().json("{\"taskId\":\""+ID+"\",\"input\":\"任务\",\"taskType\":\"knowledge_qa\",\"releaseId\":\"demo-408-v1\",\"context\":{}}"))
            .andRespond(withSuccess("{\"taskId\":\""+ID+"\",\"status\":\"completed\",\"mode\":\"demo\",\"answer\":\"结果\",\"steps\":[],\"sources\":[],\"followUp\":[],\"latencyMs\":1,\"releaseId\":\"demo-408-v1\",\"data\":{}}",MediaType.APPLICATION_JSON));
        assertEquals("结果",client.run(ID,"任务").answer()); server.verify();
    }
    @Test void rejectsForeignTaskId() {
        var builder=RestClient.builder().baseUrl("http://agent.test"); var server=MockRestServiceServer.bindTo(builder).build(); var client=new AgentClient(builder.build());
        server.expect(requestTo("http://agent.test/internal/run")).andRespond(withSuccess("{\"taskId\":\"other\",\"status\":\"completed\",\"mode\":\"demo\",\"answer\":\"结果\",\"steps\":[],\"sources\":[],\"followUp\":[]}",MediaType.APPLICATION_JSON));
        assertThrows(IllegalStateException.class,()->client.run(ID,"任务"));
    }
}
