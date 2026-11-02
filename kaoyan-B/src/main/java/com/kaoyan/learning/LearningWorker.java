package com.kaoyan.learning;

import com.kaoyan.common.ApiException;
import com.kaoyan.service.ChatRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.transaction.support.TransactionTemplate;
import static com.kaoyan.learning.ManagedPracticeService.*;

/** DB-backed polling; remote calls run outside the event/profile transaction. */
@Component
@Slf4j
@RequiredArgsConstructor
@ConditionalOnProperty(name="kaoyan.learning.enabled", havingValue="true")
public class LearningWorker {
    private final ChatRepository db;
    private final LearningProfiles profiles;
    private final LearningRecommendations recommendations;
    private final TransactionTemplate tx;
    @Scheduled(fixedDelayString="${kaoyan.learning.poll-ms:5000}",initialDelayString="${kaoyan.learning.initial-delay-ms:5000}")
    public void tick() {
        for(var row:db.rows("SELECT DISTINCT user_id FROM learning_event WHERE state='PENDING' AND next_at<=? AND attempts<3 ORDER BY user_id LIMIT 20",now())) {
            long owner=((Number)row.get("userId")).longValue();
            try {tx.executeWithoutResult(status -> {
                profiles.lock(owner);
                var events=db.rows("SELECT id FROM learning_event WHERE user_id=? AND state='PENDING' AND next_at<=? AND attempts<3 FOR UPDATE",owner,now());
                if(events.isEmpty())return;
                profiles.recompute(owner);
                for(var event:events)db.jdbc().update("UPDATE learning_event SET state='DONE' WHERE id=?",event.get("id"));
            });} catch(Exception e) {
                log.warn("learningProjectionFailure={}",e.getClass().getSimpleName());
                db.jdbc().update("UPDATE learning_event SET attempts=attempts+1,next_at=? WHERE user_id=? AND state='PENDING'",now().plusSeconds(30),owner);
            }
        }
    }
    @Scheduled(fixedDelayString="${kaoyan.learning.recommend-poll-ms:60000}",initialDelayString="${kaoyan.learning.initial-delay-ms:5000}")
    public void recommend() {
        var enabled=db.rows("SELECT user_id FROM learning_recommendation_settings WHERE enabled=1 ORDER BY user_id");
        if(enabled.isEmpty())return;String release=recommendations.release();
        for(var row:enabled) {
            long owner=((Number)row.get("userId")).longValue();
            try {recommendations.run(owner,release);} catch(ApiException e) {
                if(e.getHttpStatus()==429) db.jdbc().update("UPDATE learning_recommendation_settings SET not_before=? WHERE user_id=?",now().plusMinutes(1),owner);
                else log.warn("learningRecommendFailure={}",e.getClass().getSimpleName());
            } catch(Exception e) {log.warn("learningRecommendFailure={}",e.getClass().getSimpleName());}
        }
    }
}
