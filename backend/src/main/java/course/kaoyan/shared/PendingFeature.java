package course.kaoyan.shared;

/** 骨架的业务边界：不写库、不模拟正式结果。 */
public final class PendingFeature {
    private PendingFeature() {}
    public static ApiException error(String module) {
        return new ApiException(501, "FEATURE_NOT_IMPLEMENTED", module + "正在开发中，当前版本仅提供接口契约");
    }
}
