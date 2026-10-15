package com.kaoyan.feign;

import com.kaoyan.dto.agent.AgentRequest;
import com.kaoyan.dto.agent.AgentResponse;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;

/**
 * FastAPI Agent 远程调用客户端。
 * Internal service only; all calls carry the shared credential.
 */
@FeignClient(name = "agent", url = "${kaoyan.agent.base-url:http://127.0.0.1:8001}")
public interface AgentFeignClient {

    @PostMapping(value = "/internal/rag/chat", consumes = MediaType.APPLICATION_JSON_VALUE)
    AgentResponse chat(
            @RequestHeader("X-Internal-Key") String internalKey,
            @RequestBody AgentRequest request);
}
