package com.kaoyan.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.kaoyan.common.AgentValidationException;
import com.kaoyan.common.AgentValidationException.Code;
import com.kaoyan.config.AgentProperties;
import com.kaoyan.dto.agent.AgentResponse;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;
import java.io.InputStream;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.regex.Pattern;

@Component
public final class ReferenceSourcePolicy {
    private static final Pattern HOST = Pattern.compile(
        "[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*");
    private final Set<String> allowedHosts;

    public ReferenceSourcePolicy(AgentProperties properties, ObjectMapper json) {
        try {
            String configured = properties.getSourcePolicyFile();
            Path path = configured.isEmpty() ? null : Path.of(configured);
            if (path != null && !path.isAbsolute()) throw new IllegalArgumentException();
            try (InputStream input = path == null ? new ClassPathResource("reference-hosts.json").getInputStream()
                    : Files.newInputStream(path)) {
                var policy = json.reader().with(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).readTree(input);
                var hosts = policy.get("allowedHosts");
                if (!policy.isObject() || policy.size() != 1 || hosts == null || !hosts.isArray() || hosts.isEmpty())
                    throw new IllegalArgumentException();
                Set<String> parsed = new HashSet<>();
                for (var item : hosts) {
                    if (!item.isTextual()) throw new IllegalArgumentException();
                    String host = item.asText().toLowerCase(Locale.ROOT);
                    if (host.length() > 253 || !HOST.matcher(host).matches()) throw new IllegalArgumentException();
                    parsed.add(host);
                }
                allowedHosts = Set.copyOf(parsed);
            }
        } catch (Exception ignored) {
            // No cause: parser diagnostics can contain arbitrary configuration text.
            throw new IllegalStateException("SOURCE_POLICY_INVALID");
        }
    }

    public void validateResponse(AgentResponse response) {
        if (!"SUCCESS".equals(response.getStatus())) return;
        for (Object item : response.getReferences()) {
            if (!(item instanceof Map<?, ?> reference) || !(reference.get("url") instanceof String url))
                throw new AgentValidationException(Code.RESULT_VALIDATION_FAILED);
            validateUrl(url);
        }
    }

    public void validateUrl(String url) {
        URI uri;
        try {
            uri = URI.create(url);
            if (!"https".equals(uri.getScheme()) || uri.getHost() == null || uri.getRawUserInfo() != null
                    || uri.getPort() == 0 || uri.getPort() > 65535)
                throw new IllegalArgumentException();
        } catch (IllegalArgumentException error) {
            throw new AgentValidationException(Code.RESULT_VALIDATION_FAILED);
        }
        if (!allowedHosts.contains(uri.getHost().toLowerCase(Locale.ROOT)))
            throw new AgentValidationException(Code.SOURCE_HOST_NOT_ALLOWED);
    }
}
