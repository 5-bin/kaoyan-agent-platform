package com.kaoyan.learning;

import com.kaoyan.entity.PracticeRecord;
import com.kaoyan.learning.LearningContracts.*;
import java.time.*;
import java.util.*;

/** Pure replayable baseline; no model, clock, database or mutable parameters. */
public final class LearningProfileEngine {
    public record Evidence(PracticeRecord record,Integer hintLevel) {}
    public static String pointId(String subject,String point) { return ManagedPracticeService.hash(subject+":"+point).substring(0,24); }
    private static final class Bucket {
        String id,subject,point,difficulty;int assisted,unknown;double weight;
        List<PracticeRecord> independent=new ArrayList<>();
    }
    public Profile calculate(List<Evidence> evidence,List<Cell> cells,String blueprint,int revision,LocalDateTime at) {
        Map<String,Bucket> buckets=new TreeMap<>();
        for(var cell:cells) {
            Bucket b=bucket(cell.subject(),cell.knowledgePoint(),cell.difficulty());b.id=cell.knowledgePointId();b.weight=cell.weight();
            buckets.put(b.id+":"+b.difficulty,b);
        }
        var sorted=evidence.stream().filter(e -> valid(e.record())).sorted(Comparator
            .comparing((Evidence e) -> e.record().getAnsweredAt()).thenComparing(e -> e.record().getId())).toList();
        Map<Long,LocalDateTime> accepted=new HashMap<>();
        for(var e:sorted) {
            var r=e.record();var s=r.getQuestionSnapshot();String subject=(String)s.get("subject"),point=(String)s.get("knowledgePoint"),difficulty=(String)s.get("difficulty");
            Bucket temp=bucket(subject,point,difficulty);
            Bucket b=buckets.computeIfAbsent(temp.id+":"+difficulty,k -> temp);
            if(e.hintLevel()==null) {b.unknown++;continue;}
            if(e.hintLevel()>0) {b.assisted++;continue;}
            var previous=accepted.get(r.getQuestionId());
            if(previous!=null&&r.getAnsweredAt().isBefore(previous.plusDays(7)))continue;
            accepted.put(r.getQuestionId(),r.getAnsweredAt());b.independent.add(r);
            if(b.independent.size()>50)b.independent.remove(0);
        }
        List<Group> groups=new ArrayList<>();int samples=0,assisted=0,unknown=0;double coverage=0,score=0;
        for(Bucket b:buckets.values()) {
            int n=b.independent.size(),correct=(int)b.independent.stream().filter(r -> r.getIsCorrect()==1).count();
            Double mastery=n==0?null:(correct+1.0)/(n+2.0);
            boolean anomaly=n>=7&&b.independent.get(n-1).getIsCorrect()==0&&b.independent.get(n-2).getIsCorrect()==0
                && b.independent.subList(0,n-2).stream().filter(r -> r.getIsCorrect()==1).count()/(double)(n-2)>=0.8;
            groups.add(new Group(b.id,b.subject,b.point,b.difficulty,n,correct,b.assisted,b.unknown,mastery,
                n==0?"NOT_DIAGNOSED":n<5?"INSUFFICIENT":"SUFFICIENT",b.weight,mastery==null?null:b.weight*(1-mastery),anomaly));
            samples+=n;assisted+=b.assisted;unknown+=b.unknown;
            if(n>0&&b.weight>0) {coverage+=b.weight;score+=b.weight*mastery;}
        }
        boolean complete=!cells.isEmpty()&&coverage>=0.999999;
        boolean sufficient=complete&&groups.stream().filter(g -> g.weight()>0).allMatch(g -> g.samples()>=5);
        groups.sort(Comparator.comparing((Group g) -> g.priority()==null?-1:g.priority()).reversed().thenComparing(Group::knowledgePointId).thenComparing(Group::difficulty));
        List<String> notices=new ArrayList<>(List.of("实验性规则指数与参考分，未经完整408试卷校准，不代表录取概率。"));
        if(cells.isEmpty())notices.add("尚无审核估分蓝图；仅展示分知识点表现，不输出完整408参考分。");
        else if(!complete)notices.add("必要知识点或难度证据未覆盖，不放大已覆盖部分。");
        if(unknown>0)notices.add("旧记录的提示辅助状态未知，未计入独立证据。");
        if(samples>0&&sorted.stream().map(e -> e.record().getAnsweredAt()).max(Comparator.naturalOrder()).orElse(at).isBefore(at.minusDays(30)))notices.add("超过30天未产生有效证据，建议复测；未直接判定遗忘。");
        return new Profile(revision,"learning-v1",blueprint,complete?Math.round(1500*score)/10.0:null,
            Math.round(coverage*10000)/10000.0,samples,assisted,unknown,sufficient,samples==0?"NOT_DIAGNOSED":"ACTIVE",at.toString(),groups,notices);
    }
    private Bucket bucket(String subject,String point,String difficulty) {
        var b=new Bucket();b.subject=subject;b.point=point;b.difficulty=difficulty;b.id=pointId(subject,point);return b;
    }
    private boolean valid(PracticeRecord r) {
        var s=r.getQuestionSnapshot();return "valid".equals(r.getGradingStatus())&&r.getIsCorrect()!=null&&r.getAnsweredAt()!=null
            && s!=null&&s.get("id") instanceof Number id&&id.longValue()==r.getQuestionId()
            &&s.get("version") instanceof Number&&s.get("answer") instanceof String&&s.get("content") instanceof String
            &&s.get("subject") instanceof String&&s.get("knowledgePoint") instanceof String&&s.get("difficulty") instanceof String;
    }
}
