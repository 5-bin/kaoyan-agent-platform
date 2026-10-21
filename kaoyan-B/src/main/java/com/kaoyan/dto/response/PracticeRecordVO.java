package com.kaoyan.dto.response;

import com.kaoyan.entity.PracticeRecord;
import java.time.LocalDateTime;

/** Never expose the raw grading snapshot through session detail. */
public record PracticeRecordVO(Long id, String sessionId, Long questionId, Integer orderIndex,
        String userAnswer, Integer isCorrect, String gradingStatus, LocalDateTime answeredAt) {
    public static PracticeRecordVO from(PracticeRecord r) {
        return new PracticeRecordVO(r.getId(), r.getSessionId(), r.getQuestionId(), r.getOrderIndex(),
            r.getUserAnswer(), r.getIsCorrect(), r.getGradingStatus(), r.getAnsweredAt());
    }
}
