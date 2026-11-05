package com.kaoyan.util;

import com.aliyun.oss.OSS;
import com.aliyun.oss.OSSException;
import com.aliyun.oss.ClientException;
import com.aliyun.oss.OSSClientBuilder;
import com.kaoyan.common.ApiException;
import com.kaoyan.config.OssProperties;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.util.regex.Pattern;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.Set;
import com.aliyun.oss.model.OSSObject;

/**
 * 阿里云 OSS 上传 / 删除 / 生成 URL
 */
@Component
@RequiredArgsConstructor
public class OssUtil {

    /** 单文件大小上限 5MB */
    private static final long MAX_SIZE = 5L * 1024 * 1024;

    /** 允许的图片扩展名 */
    private static final Set<String> ALLOWED_EXT = Set.of("jpg", "jpeg", "png", "gif", "webp");

    private static final DateTimeFormatter DATE_FMT = DateTimeFormatter.ofPattern("yyyyMMdd");

    private final OssProperties props;

    private OSS ossClient;

    @PostConstruct
    public void init() {
        props.normalizedKeyPrefix();
        if (!org.springframework.util.StringUtils.hasText(props.getEndpoint())
                || !org.springframework.util.StringUtils.hasText(props.getAccessKeyId())
                || !org.springframework.util.StringUtils.hasText(props.getAccessKeySecret())
                || !org.springframework.util.StringUtils.hasText(props.getBucketName())) return;
        this.ossClient = new OSSClientBuilder()
                .build(props.getEndpoint(), props.getAccessKeyId(), props.getAccessKeySecret());
    }

    @PreDestroy
    public void destroy() {
        if (ossClient != null) {
            ossClient.shutdown();
        }
    }

    /**
     * 上传文件，返回 objectKey
     *
     * @param file   上传文件
     * @param module 业务模块（avatar / common ...）
     * @return objectKey
     */
    public String upload(MultipartFile file, String module) {
        return upload(file, module, null);
    }

    /** 上传时将对象路径绑定到当前账号，删除据此校验归属。 */
    public String upload(MultipartFile file, String module, Long userId) {
        requireConfigured();
        if (file == null || file.isEmpty()) {
            throw new ApiException(400, 400, "文件不能为空");
        }
        if (file.getSize() > MAX_SIZE) {
            throw new ApiException(400, 400, "文件过大");
        }
        String original = file.getOriginalFilename();
        String ext = "";
        if (original != null && original.contains(".")) {
            ext = original.substring(original.lastIndexOf('.') + 1).toLowerCase();
        }
        if (!ALLOWED_EXT.contains(ext)) {
            throw new ApiException(400, 400, "文件类型不支持");
        }
        String safeModule = (module == null || module.isBlank())
                ? "common" : module.replaceAll("[^a-zA-Z0-9_-]", "");
        if (safeModule.isEmpty()) safeModule = "common";
        String namespace = props.normalizedKeyPrefix();
        if (!namespace.isEmpty() && (userId == null || userId <= 0)) {
            throw new ApiException(400, 400, "上传账号无效");
        }
        String ownerPath = userId != null ? userId + "/" : "";
        String objectKey = namespace + safeModule + "/" + ownerPath + LocalDate.now().format(DATE_FMT)
                + "/" + IdUtil.uuid() + "." + ext;
        try (InputStream input = file.getInputStream()) {
            ossClient.putObject(props.getBucketName(), objectKey, input);
        } catch (IOException | OSSException | ClientException e) {
            throw new ApiException(500, 500, "上传失败");
        }
        return objectKey;
    }

    /**
     * 删除本人上传的文件。只接受带本账号路径的对象键；旧版无归属路径或他人对象
     * 统一返回404且不访问OSS，当前绑定的头像需先更换才能删除。
     *
     * @param objectKey        对象键
     * @param userId           当前账号
     * @param currentAvatarUrl 当前账号已绑定的头像地址
     */
    public void delete(String objectKey, Long userId, String currentAvatarUrl) {
        requireConfigured();
        if (objectKey == null || userId == null || !objectKey.matches(
                Pattern.quote(props.normalizedKeyPrefix()) + "[a-zA-Z0-9_-]+/" + userId + "/[0-9]{8}/[a-zA-Z0-9-]+\\.(?:jpg|jpeg|png|gif|webp)")) {
            throw new ApiException(404, 404, "文件不存在");
        }
        if (buildUrl(objectKey).equals(currentAvatarUrl)) {
            throw new ApiException(409, 409, "当前头像不能删除，请先更换头像");
        }
        try {
            ossClient.deleteObject(props.getBucketName(), objectKey);
        } catch (OSSException | ClientException e) {
            throw new ApiException(500, 500, "删除失败");
        }
    }

    /**
     * 根据 objectKey 拼接访问 URL
     *
     * @param objectKey 对象键
     * @return 完整 URL
     */
    private void requireConfigured() {
        if (ossClient == null) throw new ApiException(503, 503, "文件上传服务尚未配置");
    }

    /** 只读取已保存的合法头像对象，限制返回大小。 */
    public byte[] readAvatar(String url) {
        requireConfigured();
        String namespace = props.normalizedKeyPrefix();
        String prefix = buildUrl(namespace + "avatar/");
        if (url == null || !url.startsWith(prefix)) throw new ApiException(404, 404, "头像不存在");
        String key = namespace + "avatar/" + url.substring(prefix.length());
        String owner = namespace.isEmpty() ? "(?:[0-9]+/)?" : "[0-9]+/";
        if (!key.matches(Pattern.quote(namespace) + "avatar/" + owner + "[0-9]{8}/[a-zA-Z0-9-]+\\.(?:jpg|jpeg|png|gif|webp)")) {
            throw new ApiException(404, 404, "头像不存在");
        }
        try (OSSObject object = ossClient.getObject(props.getBucketName(), key)) {
            byte[] bytes = object.getObjectContent().readNBytes((int) MAX_SIZE + 1);
            if (bytes.length > MAX_SIZE) throw new ApiException(400, 400, "头像文件过大");
            return bytes;
        } catch (IOException | OSSException | ClientException e) {
            throw new ApiException(503, 503, "头像读取失败");
        }
    }

    /** 仅允许绑定本账号新上传的头像，或保留本人已有头像。 */
    public boolean isAllowedAvatar(String url, Long userId, String currentUrl) {
        if (url == null || url.isBlank()) return true;
        String namespace = props.normalizedKeyPrefix();
        if (namespace.isEmpty() && url.equals(currentUrl)) return true;
        if (ossClient == null || userId == null || userId <= 0) return false;
        String prefix = buildUrl(namespace + "avatar/" + userId + "/");
        if (!url.startsWith(prefix)) return false;
        return url.substring(prefix.length()).matches("[0-9]{8}/[a-zA-Z0-9-]+\\.(?:jpg|jpeg|png|gif|webp)");
    }

    public String buildUrl(String objectKey) {
        requireConfigured();
        String prefix = props.getUrlPrefix();
        if (prefix == null || prefix.isBlank()) {
            String host = props.getEndpoint()
                    .replace("https://", "").replace("http://", "");
            return "https://" + props.getBucketName() + "." + host + "/" + objectKey;
        }
        return prefix.endsWith("/") ? prefix + objectKey : prefix + "/" + objectKey;
    }
}
