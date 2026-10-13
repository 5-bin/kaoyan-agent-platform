package course.kaoyan.study;

import course.kaoyan.catalog.QuestionRepository;
import course.kaoyan.pojo.dto.study.StudyContracts;
import course.kaoyan.pojo.entity.practice.*;
import course.kaoyan.practice.PracticeAttemptRepository;
import java.time.*;
import java.util.*;
import org.springframework.stereotype.Service;

@Service
public class StudyService {
    private static final ZoneId DISPLAY_ZONE = ZoneId.of("Asia/Shanghai");
    private final PracticeAttemptRepository attempts;
    private final QuestionRepository questions;
    public StudyService(PracticeAttemptRepository attempts, QuestionRepository questions) {
        this.attempts = attempts; this.questions = questions;
    }

    public StudyContracts.Summary summary(String owner, LocalDate from, LocalDate to) {
        List<PracticeAttempt> records = attempts.findByOwnerIdAndGradingStatusOrderByCreatedAtAsc(owner, "valid");
        if (from != null) {
            Instant start = from.atStartOfDay(DISPLAY_ZONE).toInstant();
            records = records.stream().filter(a -> !a.createdAt.isBefore(start)).toList();
        }
        if (to != null) {
            Instant end = to.plusDays(1).atStartOfDay(DISPLAY_ZONE).toInstant();
            records = records.stream().filter(a -> a.createdAt.isBefore(end)).toList();
        }
        long correct = records.stream().filter(a -> a.correct).count();
        List<PracticeAttempt> independent = records.stream().filter(a -> a.hintLevelUsed == 0).toList();
        long independentCorrect = independent.stream().filter(a -> a.correct).count();
        Map<String,List<PracticeAttempt>> grouped = new LinkedHashMap<>();
        for (PracticeAttempt attempt : records) {
            questions.findById(attempt.questionId).ifPresent(q -> grouped.computeIfAbsent(q.knowledgePointId, ignored -> new ArrayList<>()).add(attempt));
        }
        List<StudyContracts.KnowledgePointStat> stats = grouped.entrySet().stream().map(entry -> {
            Question q = questions.findById(entry.getValue().get(0).questionId).orElseThrow();
            long pointCorrect = entry.getValue().stream().filter(a -> a.correct).count();
            return new StudyContracts.KnowledgePointStat(entry.getKey(), q.knowledgePointName,
                entry.getValue().size(), pointCorrect, ratio(pointCorrect, entry.getValue().size()));
        }).toList();
        return new StudyContracts.Summary(records.size(), records.stream().map(a -> a.questionId).distinct().count(),
            records.stream().filter(a -> a.hintLevelUsed > 0).count(), ratio(correct, records.size()),
            ratio(independentCorrect, independent.size()), stats);
    }
    private static Double ratio(long numerator, long denominator) {
        return denominator == 0 ? null : ((double) numerator) / denominator;
    }
}

