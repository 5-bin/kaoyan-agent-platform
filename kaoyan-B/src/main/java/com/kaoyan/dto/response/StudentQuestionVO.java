package com.kaoyan.dto.response;

import com.kaoyan.entity.Question;

/** Public question content has no answer or administrative fields. */
public record StudentQuestionVO(Long id, String subject, String knowledgePoint, String content,
        String optionA, String optionB, String optionC, String optionD, String difficulty,
        String questionType, Integer version) {
    public static StudentQuestionVO from(Question q) {
        return new StudentQuestionVO(q.getId(), q.getSubject(), q.getKnowledgePoint(), q.getContent(),
            q.getOptionA(), q.getOptionB(), q.getOptionC(), q.getOptionD(), q.getDifficulty(), q.getQuestionType(), q.getVersion());
    }
}
