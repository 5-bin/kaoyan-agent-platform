package course.kaoyan.recommendation;
import course.kaoyan.common.exception.PendingFeature;
import org.springframework.stereotype.Service;
/** 操作分派接口；领域实现需要替换下面的占位服务。 */
public interface RecommendationService {
    Object execute(String authenticatedOwner, String operation, Object input);
}
@Service
final class PendingRecommendationService implements RecommendationService {
    @Override public Object execute(String owner, String operation, Object input) {
        throw PendingFeature.error("Recommendation");
    }
}

