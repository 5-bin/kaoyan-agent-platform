package com.kaoyan.export;

import com.kaoyan.common.ApiException;
import org.springframework.stereotype.Service;
import java.io.IOException;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.Semaphore;
import static com.kaoyan.export.ExportContracts.*;

/** Creates immutable previews and downloads without additional model calls or business writes. */
@Service
public class ExportService {
    private final ExportSources sources;
    private final ExportCache cache;
    private final ExportRenderer renderer;
    private final Semaphore rendering = new Semaphore(2);
    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss XXX").withZone(ZoneId.of("Asia/Shanghai"));
    public ExportService(ExportSources sources, ExportCache cache, ExportRenderer renderer) {
        this.sources = sources; this.cache = cache; this.renderer = renderer;
    }
    public Preview create(long owner, Source source) {
        if (!rendering.tryAcquire()) throw new ApiException(429, "导出服务繁忙，请稍后重试");
        try {
            Content content = sources.build(owner, source);
            if (content.markdown().length() > 200000) throw new ApiException(413, "导出正文过长，请选择单独的计划或笔记建议");
            Instant now = Instant.now();
            String title = content.title().replaceAll("[\\p{Cntrl}]", " ").strip();
            String markdown = "# " + title.replaceAll("([\\\\`*_{}\\[\\]()#+.!|<>])", "\\\\$1") + "\n\n来源版本：" + content.version()
                    + "\n\n生成时间：" + DATE.format(now) + "\n\n" + content.markdown();
            markdown = renderer.canonicalMarkdown(markdown);
            var report = new Preview(UUID.randomUUID().toString(), title, content.version(), DATE.format(now),
                    DATE.format(now.plusSeconds(900)), markdown, content.charts());
            cache.save(owner, new Cached(now.plusSeconds(900).getEpochSecond(), source, report));
            return report;
        } finally { rendering.release(); }
    }
    public Preview get(long owner, String id) {
        Cached cached = cache.get(owner, id);
        sources.assertAvailable(owner, cached.source());
        return cached.preview();
    }
    public File file(long owner, String id, String format) {
        if (!Set.of("docx", "pdf", "md").contains(format)) throw new ApiException(400, "不支持的导出格式");
        Preview report = get(owner, id);
        if (!rendering.tryAcquire()) throw new ApiException(429, "导出服务繁忙，请稍后重试");
        try {
            byte[] bytes = renderer.render(report, format);
            if (bytes.length > 10 * 1024 * 1024) throw new ApiException(413, "导出文件超过10MiB，请缩小范围");
            // Recheck sources after rendering as well, so a completed clear cannot release an old task file.
            get(owner, id);
            String name = report.title().replaceAll("[\\p{Cntrl}\\\\/:*?\"<>|]", "_");
            if (name.length() > 60) name = name.substring(0, 60);
            String mime = switch (format) {
                case "pdf" -> "application/pdf";
                case "docx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
                default -> "text/markdown;charset=UTF-8";
            };
            return new File(bytes, name + "." + format, mime);
        } catch (IOException | IllegalArgumentException e) { throw new ApiException(503, "文件生成失败，请重试或选择其他格式"); }
        finally { rendering.release(); }
    }
}
