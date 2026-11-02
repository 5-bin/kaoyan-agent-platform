package com.kaoyan;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.export.*;
import com.kaoyan.export.ExportContracts.*;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.apache.poi.xwpf.extractor.XWPFWordExtractor;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.text.PDFTextStripper;
import org.junit.jupiter.api.Test;
import java.io.ByteArrayInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class ExportRendererTest {
    static { System.setProperty("java.awt.headless", "true"); }
    private final ExportRenderer renderer = new ExportRenderer();
    private final ObjectMapper json = new ObjectMapper();
    @Test void chineseRichTextAndChartsRemainReadableInEveryFormat() throws Exception {
        String body = """
                # 排序复习笔记

                来源版本：笔记 v3

                ## 复习重点

                **稳定排序** 保留相等元素的相对顺序，*先理解概念*。

                - 归并排序
                - 插入排序

                > 这是合成导出样例，不是正式教材。

                | 知识点 | 独立样本 | 建议 |
                | --- | --- | --- |
                | 排序 | 8 | 间隔复习 |
                | 二叉树 | 2 | 样本不足，先补充练习 |

                ```python
                def review(topic: str):
                    return "先理解，再独立练习"
                ```

                [安全来源](https://example.com/source)

                ![图片仅保留说明](https://127.0.0.1:9/tracker.png)

                <script>不可执行的原始HTML</script>
                """;
        var charts = new ExportCharts().learning(json.readTree("""
            {"from":"2026-10-03","daily":[{"statDate":"2026-10-03","questionCount":5}],
            "knowledgePoints":[{"knowledgePoint":"排序","questionCount":8},{"knowledgePoint":"二叉树","questionCount":2}]}
            """), json.readTree("{\"independentSamples\":10,\"assistedSamples\":2,\"unknownSamples\":1}"));
        body = renderer.canonicalMarkdown(body);
        assertFalse(body.contains("https://127.0.0.1:9/tracker.png"));
        assertFalse(body.contains("<script>"));
        Preview preview = new Preview("test", "排序复习笔记", "笔记 v3", "2026-11-01", "2026-11-01", body, charts);
        Path output = Path.of("target", "export-samples"); Files.createDirectories(output);
        for (String format : List.of("docx", "pdf", "md")) {
            byte[] bytes = renderer.render(preview, format);
            Files.write(output.resolve("note." + format), bytes);
            if (format.equals("docx")) {
                try (var doc = new XWPFDocument(new ByteArrayInputStream(bytes)); var extractor = new XWPFWordExtractor(doc)) {
                    String text = extractor.getText().replace("\u200B", "");
                    assertTrue(text.contains("稳定排序")); assertTrue(text.contains("样本不足"));
                    assertTrue(text.contains("图片仅保留说明")); assertEquals(3, doc.getAllPictures().size());
                }
            } else if (format.equals("pdf")) {
                try (var pdf = Loader.loadPDF(bytes)) {
                    String text = new PDFTextStripper().getText(pdf).replace("\u200B", "");
                    assertTrue(text.contains("稳定排序"), text); assertTrue(text.contains("样本不足"));
                    assertTrue(text.contains("图片仅保留说明")); assertTrue(pdf.getNumberOfPages() >= 2);
                }
            } else assertEquals(body, new String(bytes, java.nio.charset.StandardCharsets.UTF_8));
        }
    }
    @Test void fortyThousandCharactersLongTokensAndMultiPageTablesAreNotLost() throws Exception {
        Files.createDirectories(Path.of("target/export-samples"));
        StringBuilder markdown = new StringBuilder("# 长文笔记\n\n| 知识点 | 说明 |\n| --- | --- |\n");
        for (int i = 0; i < 90; i++) markdown.append("| 知识点").append(i).append(" | 分页表格内容 |\n");
        markdown.append("\n```text\n").append("x".repeat(600)).append("\n```\n\n");
        while (markdown.length() < 39750) markdown.append("独立复习记录，先理解概念，再核对例题。".repeat(10)).append("\n\n");
        markdown.append("补".repeat(40000 - markdown.length() - "全文结束标记".length())).append("全文结束标记");
        assertEquals(40000, markdown.length());
        Preview preview = new Preview("long", "长文", "v1", "now", "later", markdown.toString(), List.of());
        byte[] pdf = renderer.render(preview, "pdf");
        Files.write(Path.of("target/export-samples/long.pdf"), pdf);
        try (var document = Loader.loadPDF(pdf)) {
            String text = new PDFTextStripper().getText(document).replace("\u200B", "");
            assertTrue(text.contains("知识点89")); assertTrue(text.contains("全文结束标记"));
            assertTrue(document.getNumberOfPages() > 3);
        }
        byte[] word = renderer.render(preview, "docx");
        Files.write(Path.of("target/export-samples/long.docx"), word);
        // Inspect our own generated XML directly: repetitive 40K text can legitimately
        // exceed POI's untrusted-input compression-ratio heuristic. Never relax that global limit.
        try (var zip = new java.util.zip.ZipInputStream(new ByteArrayInputStream(word))) {
            java.util.zip.ZipEntry entry;
            boolean found = false;
            while ((entry = zip.getNextEntry()) != null) if (entry.getName().equals("word/document.xml")) {
                String xml = new String(zip.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
                assertTrue(xml.contains("全文结束标记"));
                assertEquals(91, xml.split("<w:tr>", -1).length - 1); found = true;
            }
            assertTrue(found);
        }
    }
    @Test void rejectExtraFieldsAndWrongSourceShapes() throws Exception {
        for (String value : List.of("{}", "{\"source\":\"LEARNING_REPORT\",\"userId\":2}",
                "{\"source\":\"NOTE\",\"documentId\":\"x\",\"version\":1.5}",
                "{\"source\":\"TASK_RESULT\",\"taskId\":\"x\",\"part\":\"RAW_INPUT\"}"))
            assertThrows(com.kaoyan.common.ApiException.class, () -> Source.parse(json.readTree(value)));
    }
}
