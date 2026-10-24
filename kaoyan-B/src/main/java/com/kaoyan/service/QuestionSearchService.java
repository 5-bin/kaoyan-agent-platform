package com.kaoyan.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.config.AgentProperties;
import com.kaoyan.entity.Question;
import com.kaoyan.mapper.QuestionMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.*;

/** Java chooses the authorized candidates; Python only ranks this explicit set. */
@Service
@RequiredArgsConstructor
public class QuestionSearchService {
    private final QuestionMapper questions;
    private final AgentProperties properties;
    private final ObjectMapper json;
    private final HttpClient http=HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(2)).build();
    public record Result(String status,String releaseId,List<Map<String,Object>> matches) {}

    public List<Question> published() {
        return questions.selectList(new LambdaQueryWrapper<Question>().eq(Question::getActive,1)
            .eq(Question::getReviewStatus,"APPROVED").orderByAsc(Question::getId));
    }

    public static Map<String,Object> snapshot(Question q) {
        Map<String,Object> out=new LinkedHashMap<>();out.put("id",q.getId());out.put("version",q.getVersion());
        out.put("subject",Objects.toString(q.getSubject(),""));out.put("difficulty",Objects.toString(q.getDifficulty(),""));
        out.put("knowledgePoint",Objects.toString(q.getKnowledgePoint(),""));out.put("content",Objects.toString(q.getContent(),""));
        out.put("optionA",Objects.toString(q.getOptionA(),""));out.put("optionB",Objects.toString(q.getOptionB(),""));
        out.put("optionC",Objects.toString(q.getOptionC(),""));out.put("optionD",Objects.toString(q.getOptionD(),""));return out;
    }

    public Result search(String topic,List<Map<String,Object>> candidates) {
        try {
            if(candidates.isEmpty())return new Result("READY",null,List.of());
            var publicRows=published().stream().map(QuestionSearchService::snapshot).toList();
            var index=post("/index",Map.of("questions",publicRows),5);
            String release=Objects.toString(index.get("releaseId"),"");
            if(!release.matches("questions-[a-f0-9]{32}"))throw new IllegalStateException("invalid_release");
            String state=Objects.toString(index.get("status"),"FAILED");
            if(!"READY".equals(state))return new Result(Set.of("BUILDING","BUSY").contains(state)?state:"FAILED",release,List.of());
            Map<Long,Map<String,Object>> published=new LinkedHashMap<>();
            for(var row:publicRows)published.put(((Number)row.get("id")).longValue(),row);
            List<Map<String,Object>> overrides=new ArrayList<>();
            Map<Long,Map<String,Object>> allowed=new LinkedHashMap<>();
            for(var row:candidates){
                Long id=((Number)row.get("id")).longValue();allowed.put(id,row);
                if(!row.equals(published.get(id)))overrides.add(row);
            }
            var response=post("/search",Map.of("releaseId",release,"query",topic,"allowedIds",new ArrayList<>(allowed.keySet()),"overrides",overrides),14);
            if(!release.equals(response.get("releaseId"))||!(response.get("matches") instanceof List<?> raw))throw new IllegalStateException("invalid_matches");
            List<Map<String,Object>> matches=new ArrayList<>();Set<Long> seen=new HashSet<>();
            for(Object value:raw){
                if(!(value instanceof Map<?,?> row)||!(row.get("id") instanceof Number id))throw new IllegalStateException("invalid_match");
                Long key=id.longValue();var candidate=allowed.get(key);
                if(candidate==null||!seen.add(key)||!Objects.equals(number(row.get("version")),number(candidate.get("version")))
                    ||!Set.of("LABEL","SEMANTIC").contains(row.get("method")))throw new IllegalStateException("unauthorized_match");
                if("LABEL".equals(row.get("method"))&&!LearningTopic.matches(topic,candidate.get("knowledgePoint")))throw new IllegalStateException("invalid_label");
                if("SEMANTIC".equals(row.get("method"))&&(!(row.get("score") instanceof Number score)||!Double.isFinite(score.doubleValue())||score.doubleValue()<0||score.doubleValue()>1.00001))throw new IllegalStateException("invalid_score");
                Map<String,Object> match=new LinkedHashMap<>();match.put("id",key);match.put("version",candidate.get("version"));
                match.put("method",row.get("method"));match.put("score",row.get("score"));matches.add(match);
            }
            return new Result("READY",release,matches);
        }catch(InterruptedException error){Thread.currentThread().interrupt();return new Result("UNAVAILABLE",null,List.of());}
        catch(Exception error){return new Result("UNAVAILABLE",null,List.of());}
    }

    private static Long number(Object value){return value instanceof Number n?n.longValue():null;}
    private Map<String,Object> post(String suffix,Map<String,Object> body,int timeout) throws Exception {
        byte[] data=json.writeValueAsBytes(body);
        if(data.length>16*1024*1024)throw new IllegalStateException("question_snapshot_too_large");
        var response=http.send(HttpRequest.newBuilder(URI.create(properties.getBaseUrl()+"/internal/rag/questions"+suffix))
            .timeout(Duration.ofSeconds(timeout)).header("Content-Type","application/json").header("X-Internal-Key",properties.getInternalKey())
            .POST(HttpRequest.BodyPublishers.ofByteArray(data)).build(),HttpResponse.BodyHandlers.ofString());
        if(response.statusCode()!=200||response.body().length()>4*1024*1024)throw new IllegalStateException("question_search_failed");
        return json.readValue(response.body(),new TypeReference<LinkedHashMap<String,Object>>(){});
    }
}
