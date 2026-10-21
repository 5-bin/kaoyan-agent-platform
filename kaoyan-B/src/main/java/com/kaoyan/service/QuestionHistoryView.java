package com.kaoyan.service;

import com.kaoyan.dto.response.QuestionContentVO;
import com.kaoyan.entity.PracticeRecord;
import com.kaoyan.entity.Question;
import java.util.Map;

/** Select the historical source before projecting any fields; never mix versions. */
public final class QuestionHistoryView {
    private QuestionHistoryView() {}
    public static void populate(QuestionContentVO view, PracticeRecord record, Question current) {
        if (record == null || record.getIsCorrect() == null) {
            if ((record != null && !"valid".equals(record.getGradingStatus())) || !playable(current)) {
                view.setSnapshotStatus("UNAVAILABLE"); return;
            }
            view.setSubject(current.getSubject()); view.setKnowledgePoint(current.getKnowledgePoint());
            view.setContent(current.getContent()); view.setOptionA(current.getOptionA()); view.setOptionB(current.getOptionB());
            view.setOptionC(current.getOptionC()); view.setOptionD(current.getOptionD()); view.setDifficulty(current.getDifficulty());
            view.setVersion(current.getVersion()); view.setSnapshotStatus("NOT_ANSWERED"); return;
        }
        if (!"valid".equals(record.getGradingStatus())) { view.setSnapshotStatus("UNAVAILABLE"); return; }
        Map<String,Object> s = record.getQuestionSnapshot();
        if (s == null || s.isEmpty() || !(s.get("id") instanceof Number id)
                || id.longValue() != record.getQuestionId() || text(s,"content") == null || text(s,"answer") == null) {
            view.setSnapshotStatus("MISSING"); return;
        }
        view.setSubject(text(s,"subject")); view.setKnowledgePoint(text(s,"knowledgePoint"));
        view.setContent(text(s,"content")); view.setOptionA(text(s,"optionA")); view.setOptionB(text(s,"optionB"));
        view.setOptionC(text(s,"optionC")); view.setOptionD(text(s,"optionD")); view.setDifficulty(text(s,"difficulty"));
        view.setAnswer(text(s,"answer")); view.setAnalysis(text(s,"analysis"));
        if (s.get("version") instanceof Number version) view.setVersion(version.intValue());
        view.setSnapshotStatus(s.containsKey("optionA") && s.containsKey("optionB") && s.containsKey("optionC")
            && s.containsKey("optionD") && s.containsKey("difficulty") ? "AVAILABLE" : "PARTIAL");
    }
    public static boolean playable(Question q) {
        return q != null && Integer.valueOf(1).equals(q.getActive()) && "APPROVED".equals(q.getReviewStatus());
    }
    private static String text(Map<String,Object> s, String key) { return s.get(key) instanceof String value ? value : null; }
}
