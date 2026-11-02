package com.kaoyan.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.mapper.UserMapper;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import java.util.*;

/** Fixed Java-owned destinations; upstream URLs and navigation fields are never trusted. */
@Service
public class AssistantNavigation {
    public record Destination(String target, String label, String path, List<String> aliases, boolean admin) {}
    private final List<Destination> destinations;
    private final UserMapper users;

    public AssistantNavigation(ObjectMapper json, UserMapper users) {
        this.users = users;
        try (var input = new ClassPathResource("assistant-navigation.json").getInputStream()) {
            destinations = json.readValue(input, new TypeReference<List<Destination>>() {});
        } catch (Exception error) { throw new IllegalStateException("ASSISTANT_NAVIGATION_INVALID"); }
    }

    public void decorate(Long owner, Map<String,Object> result) {
        var user = users.selectById(owner);
        result.put("navigation", targets(result, user != null && "ADMIN".equals(user.getRole())));
    }

    public List<Map<String,String>> targets(Map<String,Object> result, boolean admin) {
        String answer = Objects.toString(result.get("answer"), "");
        Set<String> selected = new LinkedHashSet<>();
        for (var destination : destinations)
            if (destination.aliases().stream().anyMatch(answer::contains)) selected.add(destination.target());
        if (result.get("documentProposal") instanceof Map<?,?>) selected.add("NOTES");
        if (result.get("candidates") instanceof List<?> candidates && !candidates.isEmpty()) selected.add("SCHOOLS");
        if (result.get("evidence") instanceof List<?> evidence) for (Object raw : evidence) {
            if (raw instanceof Map<?,?> item && item.get("resource") instanceof Map<?,?> resource) {
                String target = switch (Objects.toString(resource.get("type"), "")) {
                    case "question", "practice" -> "PRACTICE";
                    case "document" -> "DOCUMENTS";
                    case "stats" -> "STATS";
                    default -> "";
                };
                selected.add(target);
            }
        }
        if (result.get("readScope") instanceof Collection<?> scopes) for (Object scope : scopes) {
            selected.add(switch (Objects.toString(scope, "")) {
                case "wrong" -> "WRONG"; case "favorite" -> "FAVORITE"; case "stats" -> "STATS";
                case "practice", "questions" -> "PRACTICE"; case "documents" -> "DOCUMENTS"; default -> "";
            });
        }
        if (result.get("actions") instanceof List<?> actions) for (Object raw : actions)
            if (raw instanceof Map<?,?> action) selected.add(switch (Objects.toString(action.get("type"), "")) {
                case "PRACTICE_CREATE" -> "PRACTICE"; case "FAVORITE_ADD", "FAVORITE_REMOVE" -> "FAVORITE";
                case "WRONG_REMOVE" -> "WRONG"; default -> "";
            });
        return destinations.stream().filter(d -> selected.contains(d.target()) && (!d.admin() || admin))
            .map(d -> Map.of("target", d.target())).toList();
    }
}
