package com.kaoyan.util;

import com.aliyun.oss.OSS;
import com.aliyun.oss.OSSClientBuilder;
import com.kaoyan.common.ApiException;
import com.kaoyan.config.OssProperties;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.Set;

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
        String objectKey = safeModule + "/" + LocalDate.now().format(DATE_FMT)
                + "/" + IdUtil.uuid() + "." + ext;
        try {
            ossClient.putObject(props.getBucketName(), objectKey, file.getInputStream());
        } catch (IOException e) {
            throw new ApiException(500, 500, "上传失败");
        }
        return objectKey;
    }

    /**
     * 按 objectKey 删除文件
     *
     * @param objectKey 对象键
     */
    public void delete(String objectKey) {
        try {
            ossClient.deleteObject(props.getBucketName(), objectKey);
        } catch (Exception e) {
            throw new ApiException(500, 500, "删除失败");
        }
    }

    /**
     * 根据 objectKey 拼接访问 URL
     *
     * @param objectKey 对象键
     * @return 完整 URL
     */
    public String buildUrl(String objectKey) {
        String prefix = props.getUrlPrefix();
        if (prefix == null || prefix.isBlank()) {
            String host = props.getEndpoint()
                    .replace("https://", "").replace("http://", "");
            return "https://" + props.getBucketName() + "." + host + "/" + objectKey;
        }
        return prefix.endsWith("/") ? prefix + objectKey : prefix + "/" + objectKey;
    }
}
