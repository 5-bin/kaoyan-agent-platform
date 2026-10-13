package course.kaoyan.practice;

import course.kaoyan.catalog.CatalogService;
import course.kaoyan.catalog.QuestionRepository;
import course.kaoyan.catalog.QuestionVersionStore;
import course.kaoyan.common.enums.DomainTypes.*;
import course.kaoyan.common.exception.ApiException;
import course.kaoyan.pojo.dto.practice.PracticeContracts;
import course.kaoyan.pojo.entity.practice.*;
import java.time.Instant;
import java.util.*;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PracticeService {
    private final QuestionRepository questions;
    private final QuestionVersionStore versions;
    private final PracticeSessionRepository sessions;
    private final PracticeSessionItemRepository items;
    private final PracticeAttemptRepository attempts;
    private final WrongQuestionRepository wrongQuestions;
    private final QuestionFavoriteRepository favorites;

    public PracticeService(QuestionRepository questions, QuestionVersionStore versions, PracticeSessionRepository sessions,
            PracticeSessionItemRepository items, PracticeAttemptRepository attempts,
            WrongQuestionRepository wrongQuestions, QuestionFavoriteRepository favorites) {
        this.questions = questions; this.versions = versions; this.sessions = sessions; this.items = items;
        this.attempts = attempts; this.wrongQuestions = wrongQuestions; this.favorites = favorites;
    }

    @Transactional
    public PracticeContracts.SessionView createSession(String owner, PracticeContracts.SessionInput input) {
        List<Question> candidates = questions.findByActiveTrueOrderByStableOrderAsc().stream()
            .filter(q -> input.subject() == null || q.subject.equals(input.subject().name()))
            .filter(q -> input.knowledgePointId() == null || q.knowledgePointId.equals(input.knowledgePointId().toString()))
            .filter(q -> input.difficulty() == null || q.difficulty.equals(input.difficulty().name()))
            .toList();
        Set<String> allowed = switch (input.mode()) {
            case wrong -> wrongQuestions.findByOwnerIdAndStatusOrderByUpdatedAtDesc(owner, "reviewing").stream()
                .map(w -> w.questionId).collect(java.util.stream.Collectors.toCollection(LinkedHashSet::new));
            case favorite -> favorites.findByOwnerIdOrderByCreatedAtDesc(owner).stream()
                .map(f -> f.questionId).collect(java.util.stream.Collectors.toCollection(LinkedHashSet::new));
            default -> null;
        };
        if (allowed != null) candidates = candidates.stream().filter(q -> allowed.contains(q.id)).toList();
        candidates = new ArrayList<>(candidates);
        if (input.mode() == PracticeMode.random) Collections.shuffle(candidates, new java.security.SecureRandom());
        int actual = Math.min(input.questionCount(), candidates.size());
        if (actual == 0) throw new ApiException(400, "EMPTY_PRACTICE_POOL", "当前筛选条件下没有可练习题目");
        for (Question q : candidates.subList(0, actual)) versions.require(q.id, q.versionId);
        PracticeSession session = sessions.saveAndFlush(new PracticeSession(owner, input.mode().name(),
            input.subject() == null ? null : input.subject().name(),
            input.knowledgePointId() == null ? null : input.knowledgePointId().toString(),
            input.difficulty() == null ? null : input.difficulty().name(), input.questionCount(), actual));
        for (int i = 0; i < actual; i++) {
            Question q = candidates.get(i);
            items.save(new PracticeSessionItem(session.id, i + 1, q.id, q.versionId));
        }
        items.flush();
        return sessionView(session, true);
    }

    public PracticeContracts.SessionPage sessions(String owner, PracticeStatus status, int page) {
        var result = status == null
            ? sessions.findByOwnerIdOrderByCreatedAtDesc(owner, PageRequest.of(page, 20))
            : sessions.findByOwnerIdAndStatusOrderByCreatedAtDesc(owner, status.name(), PageRequest.of(page, 20));
        return new PracticeContracts.SessionPage(result.stream().map(s -> sessionView(s, false)).toList(),
            page, result.getTotalPages(), result.getTotalElements());
    }

    public PracticeContracts.SessionView session(String owner, UUID id) {
        return sessionView(ownedSession(owner, id), true);
    }

    public PracticeContracts.ItemView item(String owner, UUID sessionId, UUID itemId) {
        PracticeSession session = ownedSession(owner, sessionId);
        PracticeSessionItem item = items.findByIdAndSessionId(itemId.toString(), session.id)
            .orElseThrow(() -> notFound("练习项目不存在或无权访问"));
        Question q = versions.require(item.questionId, item.questionVersionId);
        PracticeAttempt attempt = item.attemptId == null ? null : attempts.findById(item.attemptId).orElse(null);
        boolean submitted = attempt != null;
        return new PracticeContracts.ItemView(UUID.fromString(item.id), item.ordinal, UUID.fromString(q.id),
            UUID.fromString(q.versionId), Subject.valueOf(q.subject), Difficulty.valueOf(q.difficulty),
            q.knowledgePointName, q.stem, CatalogService.options(q), item.selectedOptionDraft, submitted,
            submitted ? attempt.selectedOption : null, submitted ? attempt.correct : null,
            submitted ? q.explanation : null, submitted ? q.sourceTitle : null,
            submitted ? q.sourceUrl : null, submitted ? q.sourceLocator : null,
            item.hintLevelUsed, favorites.existsByOwnerIdAndQuestionId(owner, q.id));
    }

    @Transactional
    public PracticeContracts.SessionView progress(String owner, UUID sessionId, PracticeContracts.ProgressInput input) {
        PracticeSession session = activeSession(owner, sessionId);
        if (session.revision != input.expectedRevision())
            throw new ApiException(409, "STALE_REVISION", "练习进度已更新，请刷新后重试");
        if (input.currentOrdinal() > session.actualCount)
            throw new ApiException(400, "INVALID_INPUT", "当前题号超出批次范围");
        Map<String, PracticeSessionItem> byId = new HashMap<>();
        for (PracticeSessionItem item : items.findBySessionIdOrderByOrdinalAsc(session.id)) byId.put(item.id, item);
        for (PracticeContracts.Draft draft : input.drafts()) {
            PracticeSessionItem item = byId.get(draft.itemId().toString());
            if (item == null) throw new ApiException(404, "NOT_FOUND", "草稿项目不存在或不属于该批次");
            if (item.attemptId != null) throw new ApiException(409, "ALREADY_SUBMITTED", "已提交题目不能修改草稿");
            Question q = itemQuestion(item);
            if (draft.selectedOption() != null) validateOption(q, draft.selectedOption());
            item.selectedOptionDraft = draft.selectedOption(); items.save(item);
        }
        session.currentOrdinal = input.currentOrdinal(); session.revision++;
        sessions.saveAndFlush(session);
        return sessionView(session, true);
    }

    @Transactional
    public PracticeContracts.HintView hint(String owner, UUID sessionId, UUID itemId, int level) {
        PracticeSession session = activeSession(owner, sessionId);
        PracticeSessionItem item = items.findByIdAndSessionId(itemId.toString(), session.id)
            .orElseThrow(() -> notFound("练习项目不存在或无权访问"));
        if (item.attemptId != null) throw new ApiException(409, "ALREADY_SUBMITTED", "已提交题目不能继续查看提示");
        if (level == 2 && item.hintLevelUsed < 1)
            throw new ApiException(409, "HINT_ORDER", "请先查看一级提示");
        Question q = itemQuestion(item);
        String content = level == 1 ? q.hintConcept : q.hintApproach;
        if (content == null || content.isBlank()) return new PracticeContracts.HintView(level, false, null, item.hintLevelUsed);
        item.hintLevelUsed = Math.max(item.hintLevelUsed, level); items.saveAndFlush(item);
        return new PracticeContracts.HintView(level, true, content, item.hintLevelUsed);
    }

    @Transactional
    public synchronized PracticeContracts.AttemptView submit(String owner, PracticeContracts.AttemptInput input) {
        Optional<PracticeAttempt> replay = attempts.findByOwnerIdAndClientRequestId(owner, input.clientRequestId().toString());
        if (replay.isPresent()) {
            PracticeAttempt existing = replay.get();
            boolean same = existing.questionId.equals(input.questionId().toString())
                && existing.questionVersionId.equals(input.questionVersionId().toString())
                && existing.selectedOption.equals(input.selectedOption())
                && Objects.equals(existing.sessionId, text(input.sessionId()))
                && Objects.equals(existing.sessionItemId, text(input.sessionItemId()));
            if (!same) throw new ApiException(409, "REQUEST_CONFLICT", "相同请求编号对应了不同作答");
            return attemptView(existing);
        }
        Question q;
        PracticeSession session = null; PracticeSessionItem item = null; int hintLevel = 0;
        if (input.sessionId() != null) {
            session = activeSession(owner, input.sessionId());
            item = items.findByIdAndSessionId(input.sessionItemId().toString(), session.id)
                .orElseThrow(() -> notFound("练习项目不存在或无权访问"));
            if (!item.questionId.equals(input.questionId().toString())
                    || !item.questionVersionId.equals(input.questionVersionId().toString()))
                throw new ApiException(409, "SESSION_QUESTION_MISMATCH", "题目不属于该练习项目");
            if (item.attemptId != null) throw new ApiException(409, "ALREADY_SUBMITTED", "该练习项目已经提交");
            q = itemQuestion(item);
            hintLevel = item.hintLevelUsed;
        } else {
            Question current = question(input.questionId().toString());
            if (!current.versionId.equals(input.questionVersionId().toString()))
                throw new ApiException(409, "QUESTION_VERSION_CHANGED", "题目版本不匹配，请重新获取题目");
            q = versions.require(current.id, current.versionId);
        }
        validateOption(q, input.selectedOption());
        boolean correct = q.correctOption.equals(input.selectedOption());
        PracticeAttempt attempt = attempts.saveAndFlush(new PracticeAttempt(owner, q.id, q.versionId,
            input.selectedOption(), correct, input.clientRequestId().toString(), text(input.sessionId()),
            text(input.sessionItemId()), hintLevel));
        if (item != null) {
            item.attemptId = attempt.id; item.selectedOptionDraft = null; items.save(item);
            if (items.countBySessionIdAndAttemptIdIsNotNull(session.id) == session.actualCount) complete(session);
        }
        updateWrong(owner, q.id, attempt);
        return attemptView(attempt);
    }

    public PracticeContracts.AttemptPage attempts(String owner, int page) {
        var result = attempts.findByOwnerIdOrderByCreatedAtDesc(owner, PageRequest.of(page, 20));
        return new PracticeContracts.AttemptPage(result.stream().map(this::attemptView).toList(), page,
            result.getTotalPages(), result.getTotalElements());
    }
    public PracticeContracts.AttemptView attempt(String owner, UUID id) {
        return attemptView(attempts.findByIdAndOwnerId(id.toString(), owner)
            .orElseThrow(() -> notFound("作答不存在或无权访问")));
    }

    @Transactional
    public PracticeContracts.SessionView finish(String owner, UUID id) {
        PracticeSession session = ownedSession(owner, id);
        if (session.status.equals("active")) complete(session);
        return sessionView(session, true);
    }

    public PracticeContracts.SessionResult result(String owner, UUID id) {
        PracticeSession session = ownedSession(owner, id);
        if (!session.status.equals("completed")) throw new ApiException(409, "SESSION_ACTIVE", "请先完成或结束练习");
        List<PracticeAttempt> sessionAttempts = items.findBySessionIdOrderByOrdinalAsc(session.id).stream()
            .filter(i -> i.attemptId != null).map(i -> attempts.findById(i.attemptId).orElse(null))
            .filter(Objects::nonNull).toList();
        int answered = sessionAttempts.size();
        int correct = (int) sessionAttempts.stream().filter(a -> a.correct).count();
        int hints = (int) sessionAttempts.stream().filter(a -> a.hintLevelUsed > 0).count();
        List<PracticeAttempt> independent = sessionAttempts.stream().filter(a -> a.hintLevelUsed == 0).toList();
        int independentCorrect = (int) independent.stream().filter(a -> a.correct).count();
        return new PracticeContracts.SessionResult(UUID.fromString(session.id), session.actualCount, answered,
            session.actualCount - answered, correct, answered - correct, hints, ratio(correct, answered),
            ratio(independentCorrect, independent.size()));
    }

    public PracticeContracts.WrongPage wrongQuestions(String owner, WrongStatus status, int page) {
        var result = status == null
            ? wrongQuestions.findByOwnerIdOrderByUpdatedAtDesc(owner, PageRequest.of(page, 20))
            : wrongQuestions.findByOwnerIdAndStatusOrderByUpdatedAtDesc(owner, status.name(), PageRequest.of(page, 20));
        return new PracticeContracts.WrongPage(result.stream().map(this::wrongView).toList(), page,
            result.getTotalPages(), result.getTotalElements());
    }
    public PracticeContracts.WrongView wrongQuestion(String owner, UUID id) {
        return wrongView(wrongQuestions.findByIdAndOwnerId(id.toString(), owner)
            .orElseThrow(() -> notFound("错题记录不存在或无权访问")));
    }

    public PracticeContracts.FavoritePage favorites(String owner, int page) {
        var result = favorites.findByOwnerIdOrderByCreatedAtDesc(owner, PageRequest.of(page, 20));
        return new PracticeContracts.FavoritePage(result.stream().map(this::favoriteView).toList(), page,
            result.getTotalPages(), result.getTotalElements());
    }
    @Transactional public PracticeContracts.FavoriteState favorite(String owner, UUID questionId) {
        Question q = question(questionId.toString());
        favorites.findByOwnerIdAndQuestionId(owner, q.id).orElseGet(() -> favorites.save(new QuestionFavorite(owner, q.id)));
        return new PracticeContracts.FavoriteState(questionId, true);
    }
    @Transactional public PracticeContracts.FavoriteState unfavorite(String owner, UUID questionId) {
        favorites.findByOwnerIdAndQuestionId(owner, questionId.toString()).ifPresent(favorites::delete);
        return new PracticeContracts.FavoriteState(questionId, false);
    }

    private PracticeContracts.SessionView sessionView(PracticeSession session, boolean includeItems) {
        List<PracticeContracts.SessionItemView> views = includeItems
            ? items.findBySessionIdOrderByOrdinalAsc(session.id).stream().map(i -> {
                PracticeAttempt a = i.attemptId == null ? null : attempts.findById(i.attemptId).orElse(null);
                return new PracticeContracts.SessionItemView(UUID.fromString(i.id), i.ordinal, UUID.fromString(i.questionId),
                    a != null, i.selectedOptionDraft, a == null ? null : a.correct, i.hintLevelUsed, i.availability);
            }).toList() : List.of();
        return new PracticeContracts.SessionView(UUID.fromString(session.id), PracticeMode.valueOf(session.mode),
            PracticeStatus.valueOf(session.status), session.requestedCount, session.actualCount, session.currentOrdinal,
            session.revision, session.subject == null ? null : Subject.valueOf(session.subject),
            uuid(session.knowledgePointId), session.difficulty == null ? null : Difficulty.valueOf(session.difficulty),
            session.releaseId, session.createdAt, session.finishedAt, views);
    }
    private PracticeContracts.AttemptView attemptView(PracticeAttempt attempt) {
        Question q = versions.require(attempt.questionId, attempt.questionVersionId);
        return new PracticeContracts.AttemptView(UUID.fromString(attempt.id), UUID.fromString(q.id), UUID.fromString(q.versionId),
            attempt.selectedOption, attempt.correct, attempt.hintLevelUsed, attempt.createdAt, q.explanation,
            q.sourceTitle, q.sourceUrl, q.sourceLocator, uuid(attempt.sessionId), uuid(attempt.sessionItemId));
    }
    private PracticeContracts.WrongView wrongView(WrongQuestion wrong) {
        Question q = questions.findById(wrong.questionId).orElseThrow(() -> notFound("题目不存在"));
        return new PracticeContracts.WrongView(UUID.fromString(wrong.id), UUID.fromString(q.id), q.stem,
            Subject.valueOf(q.subject), q.knowledgePointName, wrong.wrongCount, wrong.consecutiveCorrect,
            WrongStatus.valueOf(wrong.status), wrong.updatedAt, UUID.fromString(wrong.latestAttemptId));
    }
    private PracticeContracts.FavoriteView favoriteView(QuestionFavorite favorite) {
        Question q = questions.findById(favorite.questionId).orElseThrow(() -> notFound("题目不存在"));
        return new PracticeContracts.FavoriteView(UUID.fromString(q.id), q.stem, Subject.valueOf(q.subject),
            q.knowledgePointName, q.active, favorite.createdAt);
    }
    private void updateWrong(String owner, String questionId, PracticeAttempt attempt) {
        Optional<WrongQuestion> existing = wrongQuestions.findByOwnerIdAndQuestionId(owner, questionId);
        if (!attempt.correct) {
            WrongQuestion wrong = existing.orElseGet(() -> new WrongQuestion(owner, questionId, attempt.id));
            wrong.latestAttemptId = attempt.id; wrong.wrongCount++; wrong.consecutiveCorrect = 0;
            wrong.status = "reviewing"; wrong.updatedAt = Instant.now(); wrongQuestions.save(wrong);
        } else if (existing.isPresent()) {
            WrongQuestion wrong = existing.get(); wrong.latestAttemptId = attempt.id;
            if (attempt.hintLevelUsed == 0) wrong.consecutiveCorrect++;
            if (wrong.consecutiveCorrect >= 2) wrong.status = "mastered";
            wrong.updatedAt = Instant.now(); wrongQuestions.save(wrong);
        }
    }
    private PracticeSession ownedSession(String owner, UUID id) {
        return sessions.findByIdAndOwnerId(id.toString(), owner).orElseThrow(() -> notFound("练习批次不存在或无权访问"));
    }
    private PracticeSession activeSession(String owner, UUID id) {
        PracticeSession session = ownedSession(owner, id);
        if (!session.status.equals("active")) throw new ApiException(409, "SESSION_COMPLETED", "练习已经结束");
        return session;
    }
    private Question question(String id) {
        return questions.findByIdAndActiveTrue(id).orElseThrow(() -> notFound("题目不存在或已撤回"));
    }
    private Question itemQuestion(PracticeSessionItem item) {
        question(item.questionId); // Preserve the existing logical-question availability check.
        if (!"available".equals(item.availability))
            throw new ApiException(409, "QUESTION_WITHDRAWN", "该练习题目已撤回");
        return versions.require(item.questionId, item.questionVersionId);
    }
    private void validateOption(Question q, String selected) {
        if (!CatalogService.options(q).containsKey(selected)) throw new ApiException(400, "INVALID_OPTION", "选项不属于该题目");
    }
    private void complete(PracticeSession session) {
        session.status = "completed"; session.finishedAt = Instant.now(); session.revision++;
        sessions.saveAndFlush(session);
    }
    private static ApiException notFound(String message) { return new ApiException(404, "NOT_FOUND", message); }
    private static UUID uuid(String value) { return value == null ? null : UUID.fromString(value); }
    private static String text(UUID value) { return value == null ? null : value.toString(); }
    private static Double ratio(int numerator, int denominator) { return denominator == 0 ? null : ((double) numerator) / denominator; }
}

