package com.kaoyan;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.common.AgentValidationException;
import com.kaoyan.common.AgentValidationException.Code;
import com.kaoyan.config.AgentProperties;
import com.kaoyan.service.ReferenceSourcePolicy;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.core.io.ClassPathResource;
import java.nio.file.*;
import static org.junit.jupiter.api.Assertions.*;

class ReferenceSourcePolicyTest {
    @TempDir Path folder;
    final ObjectMapper json = new ObjectMapper();

    ReferenceSourcePolicy external(String value) throws Exception {
        Path path = folder.resolve("policy.json");
        Files.writeString(path, value);
        var properties = new AgentProperties(); properties.setSourcePolicyFile(path.toString());
        return new ReferenceSourcePolicy(properties, json);
    }

    @Test void packagedPolicyMatchesSingleSourceAndCoversBothCorpora() throws Exception {
        byte[] packaged;
        try (var input = new ClassPathResource("reference-hosts.json").getInputStream()) { packaged = input.readAllBytes(); }
        assertArrayEquals(Files.readAllBytes(Path.of("../config/reference-hosts.json")), packaged);
        var policy = new ReferenceSourcePolicy(new AgentProperties(), json);
        for (String file : new String[]{"corpus.json", "real-corpus-20261024-a476bf509577d904.json"}) {
            var documents = json.readTree(Files.readString(Path.of("../kaoyan-agent/knowledge", file)));
            for (var document : documents) assertDoesNotThrow(() -> policy.validateUrl(document.get("url").asText()));
        }
    }

    @Test void externalPolicyUsesExactNormalizedHostAndDoesNotMergeDefaults() throws Exception {
        var policy = external("{\"allowedHosts\":[\"FIXTURE.INVALID\"]}");
        policy.validateUrl("https://Fixture.Invalid/approved");
        for (String url : new String[]{"https://sub.fixture.invalid/x", "https://fixture.invalid.attacker.invalid/x", "https://github.com/x"}) {
            var failure = assertThrows(AgentValidationException.class, () -> policy.validateUrl(url));
            assertEquals(Code.SOURCE_HOST_NOT_ALLOWED, failure.getCode());
        }
    }

    @ParameterizedTest
    @ValueSource(strings={"null", "[]", "{}", "{\"allowedHosts\":[]}", "{\"allowedHosts\":\"github.com\"}",
        "{\"allowedHosts\":[null]}", "{\"allowedHosts\":[\"*.github.com\"]}",
        "{\"allowedHosts\":[\"https://github.com\"]}", "{\"allowedHosts\":[\"github.com:443\"]}",
        "{\"allowedHosts\":[\" github.com\"]}", "{\"allowedHosts\":[\"-github.com\"]}",
        "{\"allowedHosts\":[\"github.com\"],\"extra\":\"private-marker\"}", "private-marker",
        "{\"allowedHosts\":[\"github.com\"]} {}"})
    void malformedPolicyFailsClosedWithoutExposingInput(String value) {
        var error = assertThrows(IllegalStateException.class, () -> external(value));
        assertEquals("SOURCE_POLICY_INVALID", error.getMessage()); assertNull(error.getCause());
    }

    @Test void missingOrRelativeExternalFileDoesNotFallBack() {
        for (String path : new String[]{folder.resolve("missing.json").toString(), "relative.json"}) {
            var properties = new AgentProperties(); properties.setSourcePolicyFile(path);
            assertEquals("SOURCE_POLICY_INVALID", assertThrows(IllegalStateException.class,
                () -> new ReferenceSourcePolicy(properties, json)).getMessage());
        }
    }

    @ParameterizedTest
    @ValueSource(strings={"http://github.com/x", "javascript:alert(1)", "https:///x", "https://user@github.com/x",
        "https://github.com:invalid/x", "https://github.com:65536/x", "https://github.com:0/x", "https://github.com/\nsecret"})
    void malformedUrlsRemainRejected(String url) {
        var policy = new ReferenceSourcePolicy(new AgentProperties(), json);
        assertEquals(Code.RESULT_VALIDATION_FAILED,
            assertThrows(AgentValidationException.class, () -> policy.validateUrl(url)).getCode());
    }
}
