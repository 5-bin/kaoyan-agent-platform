package com.kaoyan.export;

import com.fasterxml.jackson.databind.JsonNode;
import com.kaoyan.common.ApiException;
import java.util.List;
import java.util.Set;

/** Whitelisted references and immutable, account-scoped export snapshots. */
public final class ExportContracts {
    private ExportContracts() {}

    public record Source(String source, String documentId, Integer version, String taskId, String part) {
        public static Source parse(JsonNode input) {
            if (input == null || !input.isObject() || !input.path("source").isTextual()) throw invalid();
            String kind = input.path("source").asText();
            Set<String> keys = switch (kind) {
                case "NOTE" -> Set.of("source", "documentId", "version");
                case "LEARNING_REPORT" -> Set.of("source");
                case "TASK_RESULT" -> Set.of("source", "taskId", "part");
                default -> throw invalid();
            };
            if (input.size() != keys.size() || !keys.stream().allMatch(input::hasNonNull)) throw invalid();
            var fields = input.fieldNames();
            while (fields.hasNext()) if (!keys.contains(fields.next())) throw invalid();
            if (kind.equals("NOTE")) {
                if (!identifier(input.get("documentId")) || !input.get("version").isIntegralNumber()
                        || !input.get("version").canConvertToInt() || input.get("version").intValue() < 1) throw invalid();
                return new Source(kind, input.get("documentId").textValue(), input.get("version").intValue(), null, null);
            }
            if (kind.equals("TASK_RESULT")) {
                if (!identifier(input.get("taskId")) || !input.get("part").isTextual()
                        || !Set.of("ANSWER", "STUDY_PLAN", "NOTE_PROPOSAL").contains(input.get("part").textValue())) throw invalid();
                return new Source(kind, null, null, input.get("taskId").textValue(), input.get("part").textValue());
            }
            return new Source(kind, null, null, null, null);
        }
        private static boolean identifier(JsonNode node) {
            return node.isTextual() && node.textValue().matches("[A-Za-z0-9_-]{1,64}");
        }
        private static ApiException invalid() { return new ApiException(400, "导出来源参数无效"); }
    }
    public record Chart(String title, String png) {}
    public record Preview(String id, String title, String sourceVersion, String generatedAt,
                          String expiresAt, String markdown, List<Chart> charts) {}
    public record Cached(long expiresEpoch, Source source, Preview preview) {}
    public record Content(String title, String version, String markdown, List<Chart> charts) {}
    public record File(byte[] bytes, String filename, String contentType) {}
}
