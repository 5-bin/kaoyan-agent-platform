package com.kaoyan.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.ClassPathResource;

import java.net.URI;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Validates local registered admission links and projects legacy checks without old evidence. */
public final class AdmissionLinksValidator {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final Map<String, Source> SOURCES = loadSources();
    private static final Pattern SCHOOL_NAME = Pattern.compile("[^\\s和与及、，。；：,;:\ufffc]{2,24}?(?:大学|学院)");
    private static final String COMMAND_PREFIX =
        "请帮我|帮我|帮忙|麻烦|请问|查询|查一下|核对|查|给我|我要|我想|想|"
        + "了解|关于|提供|看看|看|一下|推荐|找|问|和|与|及|、|的|请|官网|学校官网";

    private AdmissionLinksValidator() {}

    private record Source(String code, String name, List<String> hosts, List<String> entries, int year) {}

    private static Map<String, Source> loadSources() {
        try (var input = new ClassPathResource("admission-sources.json").getInputStream()) {
            List<Map<String, Object>> rows = JSON.readValue(input, new TypeReference<>() {});
            Map<String, Source> result = new HashMap<>();
            for (var row : rows) {
                if (!row.keySet().equals(Set.of("code", "name", "hosts", "entries", "year"))) throw invalid();
                String code = text(row.get("code"), 8);
                String name = text(row.get("name"), 255);
                if (!code.matches("[a-z]{2,8}")) throw invalid();
                if (!(row.get("year") instanceof Number year) || year.intValue() < 2000 || year.intValue() > 2100
                    || year.doubleValue() != year.intValue()) throw invalid();
                List<String> hosts = strings(row.get("hosts"), 20);
                List<String> entries = strings(row.get("entries"), 20);
                if (entries.isEmpty()) throw invalid();
                for (String entry : entries) validateUrl(entry, hosts);
                if (result.put(code, new Source(code, name, List.copyOf(hosts), List.copyOf(entries), year.intValue())) != null)
                    throw invalid();
            }
            if (result.size() != rows.size()) throw invalid();
            return Map.copyOf(result);
        } catch (Exception error) {
            throw new IllegalStateException("ADMISSION_SOURCES_INVALID");
        }
    }

    /** Public-site lookups require an explicit current request and exclude examples/guidance. */
    /** Mirrors Python ADMISSION_COMPOUND: another explicit task in an admission turn. */
    public static final Pattern COMPOUND = Pattern.compile("解释|讲解|知识问答|是什么|什么是|复习计划|学习计划|安排.{0,8}(?:复习|学习)|笔记|错题|学情|"
        + "学习情况|正确率|刷题|出题|组题|做.{0,8}题|练习|择校|推荐.{0,6}(?:院校|学校)");
    public static final String SPLIT = "本轮同时包含招生查询和其他事项，一次只能处理一类。"
        + "请先单独发送招生查询（如“查询北京大学招生信息”），再另行发送其他问题。";

    /** Single-action admission plans must not silently drop the other request. */
    public static boolean compound(String query) {
        return COMPOUND.matcher(query).find();
    }

    public static boolean requested(String query) {
        return query.matches("(?s).*(查(?:询|看)?(?:一下)?(?:学校)?官网|(?:大学|学院)\\s*(?:查|看)(?:一下)?官网|"
                + "(?:核验|核对|查询|查|给我|提供|要|看看).{0,30}(?:招生信息|招生网址|招生官网|招生公告|招生目录|官网)|"
                + "(?:招生信息|招生网址|招生官网|招生公告|招生目录)).*")
            && !query.matches("(?s).*(不要|不必|不需要|别查|别帮|示例|例如|这句话|这个指令|如何|怎么|功能介绍|假设).*")
            && !(query.matches("(?s).*((哪些|哪几|什么)(所|个)?(学校|院校|大学)|学校名单|院校名单|支持.{0,6}(学校|院校)).*")
                && query.matches("(?s).*(官网|招生网址|招生信息|核验|登记).*"));
    }

    /** Reject unregistered or model-invented plans before dispatch; links need no year or major. */
    public static void validatePlan(Map<String, Object> plan, String userQuery) {
        if (plan.containsKey("admissionCheck")) throw invalid();
        Object raw = plan.get("admissionLinks");
        boolean links = "ADMISSION_LINKS".equals(plan.get("action"));
        if (!links && raw != null) throw invalid();
        if (!links) return;
        if (!requested(userQuery) || !"NONE".equals(plan.getOrDefault("operation", "NONE"))) throw invalid();
        if (plan.containsKey("reads")
            && (!(plan.get("reads") instanceof List<?> reads) || !reads.isEmpty())) throw invalid();
        if (plan.get("steps") instanceof List<?> steps && !steps.isEmpty()) throw invalid();
        String clarification = plan.get("clarification") instanceof String value && !value.isBlank() ? value : null;
        if (clarification != null && clarification.length() > 1000) throw invalid();
        Set<String> named = explicitSchoolNames(userQuery);
        Set<String> registered = registeredSchoolNames(userQuery);
        if (raw == null) {
            if (clarification == null || (named.size() == 1 && registered.size() == 1)) throw invalid();
            return;
        }
        if (clarification != null || !(raw instanceof Map<?, ?> query)
            || !query.keySet().equals(Set.of("schoolCode"))) throw invalid();
        Source source = SOURCES.get(text(query.get("schoolCode"), 8));
        if (source == null || !named.equals(Set.of(source.name)) || registered.size() != 1
            || !normalizeSchoolText(userQuery).contains(source.name)) throw invalid();
    }

    /** Check exact wire fields and the full ordered registry set; reject every legacy result key. */
    public static void validateResult(Map<String, Object> output, Map<String, Object> plan, String releaseId) {
        if (output.containsKey("admissionCheck")) throw invalid();
        Object raw = output.get("admissionLinks");
        boolean links = "ADMISSION_LINKS".equals(plan.get("action"));
        if (raw == null) {
            // A real link-tool failure is reported as UNSUPPORTED; a successful lookup must carry links.
            if (links && plan.get("admissionLinks") instanceof Map<?, ?> && plan.get("clarification") == null
                && !"UNSUPPORTED".equals(output.get("outcome"))
                && !(output.get("candidates") instanceof List<?> candidates && !candidates.isEmpty()
                    && output.get("notice") instanceof String notice && !notice.isBlank())) throw invalid();
            return;
        }
        if (!links || plan.get("clarification") != null || !(raw instanceof Map<?, ?> result)
            || !result.keySet().equals(Set.of("schoolCode", "schoolName", "registeredYear", "entryUrls"))) throw invalid();
        try {
            if (JSON.writeValueAsBytes(raw).length > 65536) throw invalid();
        } catch (Exception error) {
            throw invalid();
        }
        String code = text(result.get("schoolCode"), 8);
        Source source = SOURCES.get(code);
        if (source == null || !Objects.equals(result.get("schoolName"), source.name)
            || !(result.get("registeredYear") instanceof Number year)
            || year.intValue() != source.year || year.doubleValue() != source.year) throw invalid();
        List<String> entries = strings(result.get("entryUrls"), 20);
        if (!entries.equals(source.entries)) throw invalid();
        if (!(plan.get("admissionLinks") instanceof Map<?, ?> query)
            || !Objects.equals(code, query.get("schoolCode"))) throw invalid();
    }

    /** Derive a legacy display projection only from the registered school, never old evidence URLs. */
    public static Map<String, Object> legacyLinks(JsonNode check) {
        if (check == null || !check.isObject()) return null;
        JsonNode code = check.path("query").path("schoolCode");
        return code.isTextual() ? links(code.asText()) : null;
    }

    /** Project any result code through the same trusted registry for display or export. */
    public static Map<String, Object> registeredLinks(String code) {
        return links(code);
    }

    /** Build a safe model-context reply for legacy admission results without old conclusions. */
    public static String legacyContextAnswer(JsonNode result) {
        Map<String, Object> links = legacyLinks(result == null ? null : result.path("admissionCheck"));
        if (links == null) {
            return "旧的招生核验结论已隐藏；该院校未在登记清单中，无安全网址。";
        }
        return "已展示" + links.get("schoolName") + "登记的招生官网链接（登记年份 "
            + links.get("registeredYear") + "）；请自行确认招生年份、专业及报考条件。";
    }

    private static Map<String, Object> links(String code) {
        Source source = SOURCES.get(code);
        if (source == null) return null;
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("schoolCode", source.code);
        value.put("schoolName", source.name);
        value.put("registeredYear", source.year);
        value.put("entryUrls", source.entries);
        return value;
    }

    private static Set<String> registeredSchoolNames(String query) {
        Set<String> names = new LinkedHashSet<>();
        String remaining = normalizeSchoolText(query);
        // Prefer complete institution names, but preserve separate mentions of
        // the shorter school when both independent admissions bodies are named.
        List<Source> ordered = SOURCES.values().stream()
            .sorted((left, right) -> Integer.compare(right.name.length(), left.name.length())).toList();
        for (Source source : ordered) {
            if (remaining.contains(source.name)) {
                names.add(source.name);
                remaining = remaining.replace(source.name, "\ufffc");
            }
        }
        return names;
    }

    public static Set<String> explicitSchoolNames(String query) {
        Set<String> names = registeredSchoolNames(query);
        String remaining = normalizeSchoolText(query);
        for (String name : names) remaining = remaining.replace(name, "\ufffc");
        Matcher matcher = SCHOOL_NAME.matcher(remaining);
        while (matcher.find()) {
            String name = cleanSchoolName(matcher.group());
            if (name.length() < 4 || !(name.endsWith("大学") || name.endsWith("学院")) || names.contains(name)) continue;
            // A trailing college after a named school is a department, not another school.
            if (name.endsWith("学院") && remaining.substring(0, matcher.start()).stripTrailing().endsWith("\ufffc")) continue;
            names.add(name);
        }
        return names;
    }

    /** Match an exact business-catalog name; no invented or best-effort URLs. */
    public static Map<String, Object> linksForName(String name) {
        return SOURCES.values().stream().filter(source -> source.name.equals(name))
                .findFirst().map(source -> links(source.code)).orElse(null);
    }

    private static String normalizeSchoolText(String query) {
        return query.replace('(', '（').replace(')', '）');
    }

    private static String cleanSchoolName(String value) {
        String previous = null;
        while (!value.isEmpty() && !value.equals(previous)) {
            previous = value;
            value = value.replaceFirst("^(?:" + COMMAND_PREFIX + ")+", "");
        }
        return value;
    }

    private static void validateUrl(String value, List<String> hosts) {
        try {
            URI uri = URI.create(value);
            if (!"https".equals(uri.getScheme()) || uri.getHost() == null || uri.getRawUserInfo() != null
                || uri.getFragment() != null || uri.getPort() != -1 && uri.getPort() != 443
                || !hosts.contains(uri.getHost())) throw invalid();
        } catch (IllegalArgumentException error) {
            throw invalid();
        }
    }

    private static List<String> strings(Object value, int max) {
        if (!(value instanceof List<?> rows) || rows.size() > max) throw invalid();
        List<String> result = new ArrayList<>();
        for (Object row : rows) result.add(text(row, 2000));
        return List.copyOf(result);
    }

    private static String text(Object value, int max) {
        if (!(value instanceof String text) || text.isBlank() || text.length() > max) throw invalid();
        return text;
    }

    private static IllegalStateException invalid() {
        return new IllegalStateException("ADMISSION_VALIDATION_FAILED");
    }
}
