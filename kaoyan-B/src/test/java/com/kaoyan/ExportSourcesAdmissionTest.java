package com.kaoyan;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.entity.Task;
import com.kaoyan.export.ExportCharts;
import com.kaoyan.export.ExportContracts.Content;
import com.kaoyan.export.ExportContracts.Source;
import com.kaoyan.export.ExportSources;
import com.kaoyan.export.ExportRenderer;
import com.kaoyan.export.ExportContracts.Preview;
import com.kaoyan.learning.LearningProfiles;
import com.kaoyan.service.PersonalDocumentService;
import com.kaoyan.service.StudyStatService;
import com.kaoyan.service.TaskService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ExportSourcesAdmissionTest {
    private final ObjectMapper json = new ObjectMapper();

    private ExportSources sources(Task task) {
        TaskService tasks = mock(TaskService.class);
        when(tasks.detail(1L, task.getId())).thenReturn(task);
        @SuppressWarnings("unchecked")
        ObjectProvider<LearningProfiles> profiles = mock(ObjectProvider.class);
        return new ExportSources(mock(PersonalDocumentService.class), mock(StudyStatService.class), profiles,
            tasks, json, mock(ExportCharts.class));
    }

    private Task task(List<String> entryUrls, String schoolCode) {
        Task task = new Task();
        task.setId("admission-export-task");
        task.setStatus("SUCCESS");
        task.setReleaseId("rag-v1-0000000000000000");
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("outcome", "UNSUPPORTED");
        result.put("explanationMode", "rules");
        result.put("resolvedTaskType", "CHAT");
        result.put("answer", "OLD_ANSWER");
        result.put("notice", "OLD_NOTICE");
        result.put("followUp", List.of("OLD_FOLLOWUP"));
        result.put("references", List.of());
        result.put("admissionCheck", Map.of(
            "query", Map.of("schoolCode", schoolCode),
            "entryUrls", entryUrls,
            "status", "DIFFERENCES",
            "limitations", List.of("OLD_LIMITATION"),
            "evidence", List.of(Map.of("excerpt", "OLD_EXCERPT", "url", entryUrls.get(0)))));
        task.setResultPayload(result);
        return task;
    }

    @Test void legacyExportUsesRegisteredLinksOnlyAndHidesOldCheckFields() {
        Task task = task(List.of("https://evil.invalid/old-admission"), "nau");
        Content content = sources(task).build(1L, new Source("TASK_RESULT", null, null, task.getId(), "ANSWER"));
        String markdown = content.markdown();
        assertTrue(markdown.contains("登记年份"));
        assertTrue(markdown.contains("2027"));
        assertTrue(markdown.contains("https://gs.nau.edu.cn/2026/0920/c4397a161925/page.htm"));
        assertTrue(markdown.contains("请自行确认招生年份、专业及报考条件"));
        assertTrue(markdown.contains("旧版招生核验的结论"));
        for (String old : List.of("OLD_ANSWER", "OLD_NOTICE", "OLD_FOLLOWUP", "OLD_LIMITATION",
            "OLD_EXCERPT", "DIFFERENCES", "https://evil.invalid/old-admission", "处理结果")) {
            assertFalse(markdown.contains(old), old);
        }
    }

    @Test void unknownLegacySchoolShowsNoArbitraryLink() {
        Task task = task(List.of("https://evil.invalid/old-admission"), "unknown");
        Content content = sources(task).build(1L, new Source("TASK_RESULT", null, null, task.getId(), "ANSWER"));
        assertTrue(content.markdown().contains("该院校未在登记清单中"));
        assertFalse(content.markdown().contains("https://evil.invalid/old-admission"));
        assertFalse(content.markdown().contains("OLD_ANSWER"));
    }

    @Test void newCompoundLinksKeepCandidateDetailsAndSafeAnswer() {
        Task task = new Task();
        task.setId("admission-compound-task");
        task.setStatus("SUCCESS");
        task.setReleaseId("rag-v1-0000000000000000");
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("outcome", "COMPLETED");
        result.put("explanationMode", "rules");
        result.put("resolvedTaskType", "CHAT");
        result.put("answer", "推荐候选与登记链接已生成。");
        result.put("references", List.of());
        result.put("candidates", List.of(Map.of(
            "programId", "nau-2027-081200", "school", "南京审计大学", "major", "计算机技术",
            "college", "计算机学院", "year", 2027, "degreeType", "professional", "region", "江苏",
            "examSubjects", List.of("101", "201", "301", "408"), "matchedConditions", List.of("专业"))));
        result.put("admissionLinks", Map.of(
            "schoolCode", "nau", "schoolName", "南京审计大学", "registeredYear", 2027,
            "entryUrls", List.of("https://gs.nau.edu.cn/", "https://gs.nau.edu.cn/2026/0920/c4397a161925/page.htm")));
        task.setResultPayload(result);
        Content content = sources(task).build(1L, new Source("TASK_RESULT", null, null, task.getId(), "ANSWER"));
        assertTrue(content.markdown().contains("推荐候选与登记链接已生成。"));
        assertTrue(content.markdown().contains("南京审计大学 · 计算机技术"));
        assertTrue(content.markdown().contains("https://gs.nau.edu.cn/2026/0920/c4397a161925/page.htm"));
        assertFalse(content.markdown().contains("https://evil.invalid/"));
    }

    @Test void savedCatalogSnapshotPrecedesLinksAndSurvivesEveryExportFormat() throws Exception {
        Task task = new Task(); task.setId("school-catalog-export"); task.setStatus("SUCCESS");
        task.setReleaseId("school-catalog-v1");
        var result = json.readTree("""
            {"outcome":"COMPLETED","explanationMode":"rules","resolvedTaskType":"CHAT","answer":"已找到库内信息。",
             "references":[],"admissionLinks":{"schoolCode":"pku"},
             "schoolCatalog":{"school":{"id":17,"name":"北京大学","province":"北京","level":"985"},
               "targetYear":2027,"availableYears":[2027],"total":1,"warnings":[],
               "details":[{"id":1,"year":2027,"majorCode":"081200","majorName":"计算机科学与技术","remark":"采集待核实",
                 "admissionMetrics":{"college":"计算机学院","track":"系统方向",
                   "enrollment":{"year":2027,"value":77,"status":"OFFICIAL","basis":"TOTAL_INCLUDING_RECOMMENDED",
                     "scopeLabel":"专业合计，各方向共用","sources":[]},
                   "cutoffReference":{"year":2026,"value":310,"status":"UNVERIFIED","basis":"NOT_APPLICABLE",
                     "scopeLabel":"普通全日制","sources":[]}}}]}}
            """);
        task.setResultPayload(json.convertValue(result, Map.class));
        var content = sources(task).build(1L, new Source("TASK_RESULT", null, null, task.getId(), "ANSWER"));
        assertTrue(content.markdown().indexOf("库内信息") < content.markdown().indexOf("招生官网链接"));
        var renderer = new ExportRenderer();
        var preview = new Preview("catalog", content.title(), content.version(), "2026-11-02", "2026-11-02",
                renderer.canonicalMarkdown(content.markdown()), List.of());
        var output = java.nio.file.Path.of("target/export-samples");
        java.nio.file.Files.createDirectories(output);
        for (String format : List.of("md", "docx", "pdf")) {
            byte[] bytes = renderer.render(preview, format);
            java.nio.file.Files.write(output.resolve("school-catalog." + format), bytes);
            String text;
            if (format.equals("pdf")) {
                try (var document = org.apache.pdfbox.Loader.loadPDF(bytes)) {
                    text = new org.apache.pdfbox.text.PDFTextStripper().getText(document);
                }
            } else if (format.equals("docx")) {
                try (var document = new org.apache.poi.xwpf.usermodel.XWPFDocument(new java.io.ByteArrayInputStream(bytes));
                     var extractor = new org.apache.poi.xwpf.extractor.XWPFWordExtractor(document)) {
                    text = extractor.getText();
                }
            } else text = new String(bytes, java.nio.charset.StandardCharsets.UTF_8);
            text = text.replace("\u200B", "").replaceAll("\\s+", "");
            assertTrue(text.contains("2027年招生计划：77人"), format);
            assertTrue(text.contains("2026年复试参考线：310分"), format);
            assertTrue(text.contains("第三方·待核实"), format);
            assertTrue(text.contains("专业合计，各方向共用"), format);
            assertTrue(text.contains("采集待核实"), format);
            assertTrue(text.indexOf("库内信息") < text.indexOf("招生官网链接"), format);
        }
    }

    @Test void missingCatalogExportsGapAndLinksWithoutInventingSchoolDetails() throws Exception {
        Task task = new Task(); task.setId("missing-catalog-export"); task.setStatus("SUCCESS");
        task.setReleaseId("school-catalog-v1");
        task.setResultPayload(json.convertValue(json.readTree("""
            {"outcome":"UNSUPPORTED","explanationMode":"rules","resolvedTaskType":"CHAT",
             "answer":"院校库尚未收录该院校的信息。","references":[],
             "schoolCatalog":{"school":null,"details":[],"total":0},"admissionLinks":{"schoolCode":"pku"}}
            """), Map.class));
        String markdown = sources(task).build(1L, new Source("TASK_RESULT", null, null, task.getId(), "ANSWER")).markdown();
        assertTrue(markdown.contains("院校库尚未收录"));
        assertTrue(markdown.contains("招生官网链接"));
        assertFalse(markdown.contains("未记录 · 库内信息"));
    }
}
