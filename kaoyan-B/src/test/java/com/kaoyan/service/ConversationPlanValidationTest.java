package com.kaoyan.service;

import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class ConversationPlanValidationTest {
    Map<String,Object> plan(Object steps) {
        return Map.of("action","MULTI_AGENT","planVersion",2,"steps",steps,"modelCallsUsed",1,"studyDays",7);
    }
    Map<String,Object> step(String name,String... dependencies) {
        return Map.of("agent",name,"dependsOn",List.of(dependencies));
    }
    @Test void targetHintsMatchTheRequestedOperation() {
        assertTrue(ConversationService.operationHint("WRONG_REMOVE").contains("移出错题"));
        assertTrue(ConversationService.operationHint("FAVORITE_REMOVE").contains("取消收藏"));
        assertTrue(ConversationService.operationHint("PRACTICE_CREATE").contains("做几道TCP题"));
        assertTrue(ConversationService.operationHint(null).contains("加入收藏"));
        for(String op:List.of("WRONG_REMOVE","FAVORITE_REMOVE","PRACTICE_CREATE","FAVORITE_ADD"))
            assertTrue(ConversationService.operationHint(op).startsWith("\n推荐问法："));
    }
    @Test void acceptsLegacyAndBoundedOrderedExperts() {
        assertDoesNotThrow(() -> ConversationService.validateExpertSteps(Map.of("action","CHAT")));
        assertDoesNotThrow(() -> ConversationService.validateExpertSteps(plan(List.of(step("LEARNING"),step("STUDY_PLAN","LEARNING"),step("SCHOOL","LEARNING")))));
    }
    @Test void rejectsUnknownRepeatedAndForwardDependencies() {
        for(var steps:List.of(List.of(step("UNTRUSTED")),List.of(step("LEARNING"),step("LEARNING")),
            List.of(step("STUDY_PLAN","LEARNING"),step("LEARNING")),List.of(step("LEARNING","LEARNING"))))
            assertThrows(IllegalStateException.class,() -> ConversationService.validateExpertSteps(plan(steps)));
        var bad=new HashMap<>(plan(List.of(step("LEARNING"))));bad.put("modelCallsUsed",2);
        assertThrows(IllegalStateException.class,() -> ConversationService.validateExpertSteps(bad));
        bad.put("modelCallsUsed",0.5);
        assertThrows(IllegalStateException.class,() -> ConversationService.validateExpertSteps(bad));
    }
    @Test void validatesStudyStructureWithoutChangingBusinessState() {
        Map<String, Object> good=Map.of("studyPlan",Map.of("basis",List.of("合成依据"),"days",List.of(Map.of("day",1,"topic","线程","tasks",List.of("核对审核资料")))));
        assertDoesNotThrow(() -> ConversationService.validateStudyPlan(good));
        assertThrows(IllegalStateException.class,() -> ConversationService.validateStudyPlan(Map.of("studyPlan",Map.of("basis",List.of(),"days",List.of(Map.of("day",2,"topic","线程","tasks",List.of("任务")))))));
        assertThrows(IllegalStateException.class,() -> ConversationService.validateStudyPlan(Map.of("studyPlan",Map.of("basis",List.of(),"days",List.of(),"ownerId",2))));
    }

    @Test void rejectsInconsistentActionsReadsAndDocumentSnapshots() {
        for(Map<String,Object> bad:List.of(
            Map.<String,Object>of("action","CHAT","reads",List.of("stats"),"clarification","补充条件"),
            Map.<String,Object>of("action","DOCUMENT_UPDATE"),
            Map.<String,Object>of("action","WRONG_QUESTION_TUTOR"),
            Map.<String,Object>of("action","STUDY_PLAN","planVersion",2,"steps",List.of(step("LEARNING"))),
            Map.<String,Object>of("action","MULTI_AGENT","planVersion",2,"steps",List.of(step("LEARNING")),"studyDays",3),
            Map.<String,Object>of("action","CHAT","operation","FAVORITE_ADD","reads",List.of("favorite")),
            Map.<String,Object>of("action","LEARNING_ANALYSIS","operation","PRACTICE_CREATE","target","normal","reads",List.of("wrong")),
            Map.<String,Object>of("action","LEARNING_ANALYSIS","reads",List.of("stats","stats"))
        )) assertThrows(IllegalStateException.class,() -> ConversationService.validatePlanConsistency(bad,Map.of()));
        assertDoesNotThrow(() -> ConversationService.validatePlanConsistency(
            Map.of("action","DOCUMENT_UPDATE"),Map.of("document",Map.of("id","selected","version",3))));
        assertDoesNotThrow(() -> ConversationService.validatePlanConsistency(
            Map.of("action","CHAT","clarification","请先选择文档"),Map.of()));
        assertDoesNotThrow(() -> ConversationService.validatePlanConsistency(
            Map.of("action","LEARNING_ANALYSIS","operation","FAVORITE_ADD","target","wrong","reads",List.of("wrong")),Map.of()));
    }

    @Test void negationDoesNotEraseSeparatePositiveRequests() {
        assertEquals("收藏 Q1",ConversationService.positiveOperationQuery("不要推荐院校，并收藏 Q1"));
        assertEquals("解释TCP",ConversationService.positiveOperationQuery("不推荐学校，解释TCP"));
        assertEquals("",ConversationService.positiveOperationQuery("不要收藏 Q1"));
    }

    @Test void validatesSectionsAgainstPlanAndPreservesLegacyResults() {
        var planned=plan(List.of(step("KNOWLEDGE"),step("PRACTICE")));
        Map<String,Object> result=new LinkedHashMap<>(Map.of("answer","知识解释与练习建议", "partial",true,"sections",List.of(
            Map.of("agent","KNOWLEDGE","outcome","COMPLETED","explanationMode","rules"),
            Map.of("agent","PRACTICE","outcome","UNSUPPORTED","explanationMode","rules","notice","题目不足"))));
        assertDoesNotThrow(() -> ConversationService.validateExpertSections(result,planned));
        assertDoesNotThrow(() -> ConversationService.validateExpertSections(Map.of("answer","旧结果"),Map.of()));
        result.put("partial",false);
        assertThrows(IllegalStateException.class,() -> ConversationService.validateExpertSections(result,planned));
        result.put("partial",true);
        assertThrows(IllegalStateException.class,() -> ConversationService.validateExpertSections(result,plan(List.of(step("PRACTICE"),step("KNOWLEDGE")))));
        ConversationService.reconcilePracticeSection(result,true,false);
        assertEquals("知识解释与练习建议",result.get("answer"));
        assertEquals(false,result.get("partial"));
        assertEquals("COMPLETED",result.get("outcome"));
        ConversationService.reconcilePracticeSection(result,false,false);
        assertEquals(true,result.get("partial"));
        assertEquals("知识解释与练习建议",result.get("answer"));
        result.put("retrievalStatus","BUILDING");
        assertFalse(ConversationService.retryableSearch(result));
        ConversationService.reconcilePracticeSection(result,false,true);
        assertTrue(ConversationService.retryableSearch(result));
        result.put("actions",List.of(Map.of("id","existing-action")));
        assertFalse(ConversationService.retryableSearch(result));
    }
    @Test void sectionFallbackReasonIsWhitelistedAndPairedWithFallback() {
        var planned=plan(List.of(step("LEARNING"),step("KNOWLEDGE")));
        Map<String,Object> learning=new LinkedHashMap<>(Map.of("agent","LEARNING","outcome","COMPLETED","explanationMode","fallback","fallbackReason","NUMBER_MISMATCH"));
        Map<String,Object> result=new LinkedHashMap<>(Map.of("answer","学情与知识","partial",false,"sections",List.of(
            learning,Map.of("agent","KNOWLEDGE","outcome","COMPLETED","explanationMode","ai"))));
        assertDoesNotThrow(() -> ConversationService.validateExpertSections(result,planned));
        learning.put("fallbackReason","UNKNOWN_CODE");
        assertThrows(IllegalStateException.class,() -> ConversationService.validateExpertSections(result,planned));
        learning.put("fallbackReason","TIMEOUT");learning.put("explanationMode","ai");
        assertThrows(IllegalStateException.class,() -> ConversationService.validateExpertSections(result,planned));
    }
    @Test void historyKeepsPendingFollowUpWithinMessageLimit() {
        assertEquals("推荐条件尚不完整。\n待补充：请选择学硕或专硕",
            ConversationService.historyAnswer(Map.of("answer","推荐条件尚不完整。","followUp",List.of("请选择学硕或专硕"))));
        assertEquals("普通回答",ConversationService.historyAnswer(Map.of("answer","普通回答")));
        String text=ConversationService.historyAnswer(Map.of("answer","长".repeat(5000),"followUp",List.of("请选择学硕或专硕")));
        assertTrue(text.endsWith("待补充：请选择学硕或专硕") && text.contains("[历史内容节选"));
        // Python rejects history messages longer than 4000 characters.
        assertTrue(text.length()<=4000);
    }
}
