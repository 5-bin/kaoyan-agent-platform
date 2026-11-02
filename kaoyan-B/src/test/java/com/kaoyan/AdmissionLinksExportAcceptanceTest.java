package com.kaoyan;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.entity.Task;
import com.kaoyan.export.ExportCharts;
import com.kaoyan.export.ExportContracts.Content;
import com.kaoyan.export.ExportContracts.Preview;
import com.kaoyan.export.ExportContracts.Source;
import com.kaoyan.export.ExportRenderer;
import com.kaoyan.export.ExportSources;
import com.kaoyan.learning.LearningProfiles;
import com.kaoyan.service.PersonalDocumentService;
import com.kaoyan.service.StudyStatService;
import com.kaoyan.service.TaskService;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.poi.xwpf.extractor.XWPFWordExtractor;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

/** User-facing export regression: persisted old verification content must never reappear. */
class AdmissionLinksExportAcceptanceTest {
    private static final String ENTRY = "https://gs.nau.edu.cn/2026/0920/c4397a161925/page.htm";
    private static final String OLD_CONCLUSION = "旧自动核验结论已确认考试科目改变";
    private static final String OLD_EXCERPT = "旧网页摘录不能再次展示";

    private Content export(Map<String, Object> payload) {
        Task task = new Task();
        task.setId("admission-export");
        task.setStatus("SUCCESS");
        task.setReleaseId("rag-v1-0000000000000000");
        task.setResultPayload(payload);
        TaskService tasks = mock(TaskService.class);
        when(tasks.detail(7L, task.getId())).thenReturn(task);
        @SuppressWarnings("unchecked") ObjectProvider<LearningProfiles> profiles = mock(ObjectProvider.class);
        ExportSources sources = new ExportSources(mock(PersonalDocumentService.class), mock(StudyStatService.class),
                profiles, tasks, new ObjectMapper(), mock(ExportCharts.class));
        return sources.build(7L, new Source("TASK_RESULT", null, null, task.getId(), "ANSWER"));
    }

    private Map<String, Object> legacy(String school) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("outcome", "COMPLETED");
        payload.put("explanationMode", "rules");
        payload.put("answer", OLD_CONCLUSION);
        payload.put("notice", OLD_CONCLUSION);
        payload.put("followUp", List.of(OLD_CONCLUSION));
        payload.put("admissionCheck", Map.of("query", Map.of("schoolCode", school),
                "entryUrls", List.of("https://evil.invalid/forged"), "status", "DIFFERENCES",
                "evidence", List.of(Map.of("excerpt", OLD_EXCERPT, "url", "https://evil.invalid/evidence")),
                "comparisons", List.of(Map.of("newValue", OLD_CONCLUSION))));
        return payload;
    }

    @Test void legacyVerificationBecomesRegisteredLinksInAllThreeFormatsWithoutChangingTheRecord() throws Exception {
        Map<String, Object> persisted = legacy("nau");
        Map<String, Object> before = new LinkedHashMap<>(persisted);
        Content content = export(persisted);
        assertEquals(before, persisted, "Export projection must not rewrite the stored history");
        assertTrue(content.markdown().contains(ENTRY));
        assertTrue(content.markdown().contains("登记年份"));
        assertTrue(content.markdown().contains("2027"));
        Preview preview = new Preview("admission", content.title(), "历史回答", "now", "later", content.markdown(), List.of());
        ExportRenderer renderer = new ExportRenderer();
        for (String format : List.of("md", "docx", "pdf")) {
            byte[] bytes = renderer.render(preview, format);
            String text;
            if (format.equals("docx")) {
                try (XWPFDocument document = new XWPFDocument(new ByteArrayInputStream(bytes));
                     XWPFWordExtractor extractor = new XWPFWordExtractor(document)) {
                    text = extractor.getText();
                    assertTrue(document.getHyperlinks().length > 0, "Word URLs must remain clickable");
                }
            } else if (format.equals("pdf")) {
                try (var document = Loader.loadPDF(bytes)) {
                    text = new PDFTextStripper().getText(document);
                    boolean clickable = false;
                    for (var page : document.getPages())
                        clickable |= page.getAnnotations().stream().anyMatch(
                                item -> item instanceof org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink);
                    assertTrue(clickable, "PDF URLs must remain clickable");
                }
            } else {
                text = new String(bytes, StandardCharsets.UTF_8);
                assertTrue(text.contains("[" + ENTRY + "](" + ENTRY + ")"));
            }
            text = text.replace("\u200B", "");
            assertTrue(text.contains("南京审计大学"), format);
            assertTrue(text.contains("请自行确认招生年份、专业及报考条件"), format);
            for (String forbidden : List.of(OLD_CONCLUSION, OLD_EXCERPT, "evil.invalid", "DIFFERENCES", "官网实时取证"))
                assertFalse(text.contains(forbidden), format + " exposed " + forbidden);
        }
    }

    @Test void unknownLegacySchoolDoesNotExposeStoredUntrustedLinks() {
        String text = export(legacy("unknown")).markdown();
        assertFalse(text.contains("evil.invalid"));
        assertFalse(text.contains(OLD_CONCLUSION));
        assertFalse(text.contains(OLD_EXCERPT));
    }

    @Test void linkProjectionKeepsCompoundRecommendationCandidates() {
        Map<String, Object> payload = legacy("nau");
        payload.put("candidates", List.of(Map.of("school", "南京审计大学", "major", "计算机科学与技术",
                "college", "计算机学院", "year", 2027, "explanation", "保留原规则候选说明")));
        String text = export(payload).markdown();
        assertTrue(text.contains("保留原规则候选说明"));
        assertTrue(text.contains("计算机科学与技术"));
        assertTrue(text.contains(ENTRY));
        assertFalse(text.contains(OLD_CONCLUSION));
    }
}
