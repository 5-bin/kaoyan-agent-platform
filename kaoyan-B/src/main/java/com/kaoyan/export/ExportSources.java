package com.kaoyan.export;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaoyan.common.ApiException;
import com.kaoyan.entity.Task;
import com.kaoyan.learning.LearningProfiles;
import com.kaoyan.service.AdmissionLinksValidator;
import com.kaoyan.service.PersonalDocumentService;
import com.kaoyan.service.StudyStatService;
import com.kaoyan.service.TaskService;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import static com.kaoyan.export.ExportContracts.*;

/** Builds reports exclusively from owner-authorized services, never client content or current question answers. */
@Component
public class ExportSources {
    private final PersonalDocumentService notes;
    private final StudyStatService stats;
    private final ObjectProvider<LearningProfiles> profiles;
    private final TaskService tasks;
    private final ObjectMapper json;
    private final ExportCharts charts;

    public ExportSources(PersonalDocumentService notes, StudyStatService stats, ObjectProvider<LearningProfiles> profiles,
                         TaskService tasks, ObjectMapper json, ExportCharts charts) {
        this.notes = notes; this.stats = stats; this.profiles = profiles;
        this.tasks = tasks; this.json = json; this.charts = charts;
    }

    public void assertAvailable(long owner, Source source) {
        if (source.source().equals("NOTE")) notes.version(owner, source.documentId(), source.version());
        if (source.source().equals("TASK_RESULT")) task(owner, source.taskId());
    }

    public Content build(long owner, Source source) {
        return switch (source.source()) {
            case "NOTE" -> {
                var note = notes.version(owner, source.documentId(), source.version());
                if (!(note.get("title") instanceof String title) || !(note.get("content") instanceof String body))
                    throw new ApiException(409, "该笔记版本格式不完整，暂不可导出");
                yield new Content(title, "笔记 v" + source.version(), body, List.of());
            }
            case "LEARNING_REPORT" -> learning(owner);
            case "TASK_RESULT" -> result(owner, source);
            default -> throw new ApiException(400, "导出来源无效");
        };
    }

    private Task task(long owner, String id) {
        Task task = tasks.detail(owner, id);
        if (!"SUCCESS".equals(task.getStatus()) || task.getResultPayload() == null)
            throw new ApiException(409, "仅支持导出已成功完成的回答");
        JsonNode result = json.valueToTree(task.getResultPayload());
        if (!result.path("answer").isTextual() || !result.path("outcome").isTextual()
                || !result.path("explanationMode").isTextual())
            throw new ApiException(409, "该历史结果格式暂不支持导出");
        return task;
    }

    private Content result(long owner, Source source) {
        Task task = task(owner, source.taskId());
        JsonNode data = json.valueToTree(task.getResultPayload());
        StringBuilder out = new StringBuilder();
        String title;
        switch (source.part()) {
            case "NOTE_PROPOSAL" -> {
                JsonNode proposal = data.path("documentProposal");
                if (!proposal.path("content").isTextual()) throw new ApiException(409, "该回答没有笔记建议");
                title = proposal.path("title").asText("笔记建议");
                out.append("> ").append(proposalStatus(owner, task.getId())).append("\n\n").append(proposal.path("content").asText());
            }
            case "STUDY_PLAN" -> {
                if (!data.path("studyPlan").isObject()) throw new ApiException(409, "该回答没有复习计划");
                title = "复习计划";
                plan(out, data.path("studyPlan"));
            }
            default -> {
                title = "考研助手回答";
                boolean legacyAdmission = data.path("admissionCheck").isObject();
                Map<String, Object> links = legacyAdmission
                        ? AdmissionLinksValidator.legacyLinks(data.path("admissionCheck"))
                        : AdmissionLinksValidator.registeredLinks(data.path("admissionLinks").path("schoolCode").asText(""));
                // Legacy admission prose may contain old conclusions; never export it.
                if (legacyAdmission) {
                    out.append(links == null
                            ? "该院校未在登记清单中，没有可展示的招生官网链接。请以院校官方渠道自行确认。"
                            : "已展示登记招生官网链接；请自行确认招生年份、专业及报考条件。").append("\n\n");
                } else {
                    out.append(data.path("answer").asText()).append("\n\n");
                    if (data.path("schoolCatalog").path("school").isObject()) catalog(out, data.path("schoolCatalog"));
                }
                if (data.path("studyPlan").isObject()) plan(out, data.path("studyPlan"));
                if (data.path("documentProposal").path("content").isTextual()) {
                    out.append("\n## 笔记建议\n\n").append(proposalStatus(owner, task.getId())).append("\n\n")
                            .append(data.path("documentProposal").path("content").asText()).append("\n\n");
                }
                for (JsonNode candidate : data.path("candidates")) {
                    out.append("\n### ").append(cell(candidate.path("school"))).append(" · ").append(cell(candidate.path("major"))).append("\n\n");
                    for (String key : List.of("college", "year", "degreeType", "region", "explanation"))
                        append(out, candidate.path(key));
                    out.append("考试科目：").append(join(candidate.path("examSubjects"))).append("\n\n");
                    strings(out, candidate.path("matchedConditions"), "符合条件：");
                    strings(out, candidate.path("pendingChecks"), "待确认：");
                }
                if (links != null) linksBlock(out, links);
                append(out, data.path("coverage"));
                if (!legacyAdmission) {
                    append(out, data.path("notice"));
                    strings(out, data.path("followUp"), "待补充：");
                }
                strings(out, data.path("weakPoints"), "本次薄弱点：");
                if (data.hasNonNull("accuracy")) out.append("有效作答正确率：").append(cell(data.get("accuracy"))).append("%（不代表考试能力）\n\n");
                if (data.hasNonNull("standardAnswer")) out.append("历史作答：题目版本 ").append(cell(data.path("questionVersion")))
                        .append("；你的选择 ").append(cell(data.path("userAnswer"))).append("；标准答案 ").append(cell(data.path("standardAnswer"))).append("。\n\n");
                if (data.path("learningSnapshot").isObject()) {
                    JsonNode snapshot = data.path("learningSnapshot");
                    out.append("推荐依据画像 v").append(cell(snapshot.path("profileRevision"))).append("；蓝图覆盖 ").append(percent(snapshot.path("coverage")))
                            .append("；408实验性参考分 ").append(cell(snapshot.path("referenceScore"))).append("（未经整卷校准，不代表录取概率）。\n\n");
                }
                for (JsonNode comparison : data.path("historicalComparisons")) {
                    out.append("历史对照：").append(cell(comparison.path("programId"))).append(" · ").append(cell(comparison.path("year")))
                            .append(" · 分数 ").append(cell(comparison.path("score"))).append(" · 实验性差值 ").append(cell(comparison.path("gap"))).append("\n\n");
                    append(out, comparison.path("notice")); append(out, comparison.path("source").path("url"));
                }
                if (legacyAdmission) out.append("\n## 回答状态与依据\n\n").append("旧版招生核验的结论、差异、证据、时间与限制已隐藏；仅保留登记院校的安全网址。\n\n");
            }
        }
        if (!data.path("admissionCheck").isObject()) {
            out.append("\n## 回答状态与依据\n\n");
            out.append("处理结果：").append(cell(data.path("outcome"))).append("；生成方式：").append(cell(data.path("explanationMode"))).append("。\n\n");
            if (data.path("partial").asBoolean()) out.append("部分事项完成，其余事项以原回答提示为准。\n\n");
            for (JsonNode section : data.path("sections")) out.append("- ").append(cell(section.path("agent"))).append("：")
                    .append(cell(section.path("outcome"))).append(" · ").append(cell(section.path("notice"))).append("\n");
            if (data.path("explanationMode").asText().equals("fallback")) out.append("\nAI 已降级，本文件保留原有规则结果及提示。\n\n");
        }
        JsonNode support = data.path("citationSupport");
        if (support.isObject()) {
            out.append("\n引用支持状态：").append(cell(support.path("status"))).append("；通过 ")
                    .append(cell(support.path("supported"))).append(" / ").append(cell(support.path("checked"))).append(" 条。此为词项核对，不等同于事实审查。\n\n");
            for (JsonNode item : support.path("items")) out.append("- ").append(cell(item.path("text"))).append(" · ")
                    .append(item.path("supported").asBoolean() ? "核对通过" : "待核对").append(" · ").append(join(item.path("sourceIds"))).append("\n");
            if (support.path("items").isEmpty()) for (JsonNode item : support.path("unsupported"))
                out.append("- 待核对：").append(cell(item.path("text"))).append(" · ").append(cell(item.path("reason"))).append("\n");
        }
        for (JsonNode evidence : data.path("evidence")) {
            out.append("\n- 学习依据 ").append(cell(evidence.path("ref"))).append("：").append(cell(evidence.path("title")))
                    .append(" · ").append(cell(evidence.path("locator"))).append(" · ").append(cell(evidence.path("version"))).append("\n");
            append(out, evidence.path("summary"));
        }
        for (JsonNode ref : data.path("references")) {
            out.append("\n### 来源 ").append(cell(ref.path("id"))).append(" · ").append(cell(ref.path("title"))).append("\n\n");
            for (String key : List.of("url", "locator", "version", "retrievedAt", "excerpt")) append(out, ref.path(key));
        }
        return new Content(title, "任务 " + task.getId() + " · 资料 " + task.getReleaseId(), out.toString(), List.of());
    }

    private String proposalStatus(long owner, String taskId) {
        Integer applied = notes.appliedVersion(owner, taskId);
        return applied == null ? "待确认建议：本次建议尚未保存为个人笔记，导出不会自动保存。"
                : "本次建议已确认保存为笔记 v" + applied + "；此处导出原始建议，后续修改以笔记页的正式版本为准。";
    }

    @SuppressWarnings("unchecked")
    private void linksBlock(StringBuilder out, Map<String, Object> links) {
        out.append("\n## 招生官网链接\n\n");
        out.append("登记院校：").append(cell(links.get("schoolName"))).append("\n\n");
        out.append("登记年份：").append(cell(links.get("registeredYear")))
                .append("（登记年份不代表网址当前内容年份或最新招生年度）\n\n");
        for (Object entry : (List<Object>) links.get("entryUrls"))
            out.append("- [").append(cell(entry)).append("](").append(entry).append(")\n");
        out.append("\n请自行确认招生年份、专业及报考条件。\n\n");
    }

    private Content learning(long owner) {
        JsonNode statistics = json.valueToTree(stats.learning(owner, null, null, null));
        StringBuilder out = new StringBuilder("## 近30天学习统计\n\n");
        out.append("统计区间：").append(statistics.path("from").asText()).append(" 至 ").append(statistics.path("to").asText())
                .append("（上海日期，含今天）。统计按有效已提交作答次数计算，画像按去重独立证据计算，二者分母不同。\n\n");
        out.append("| 指标 | 数值 |\n| --- | --- |\n");
        row(out, "有效作答次数", cell(statistics.path("questionCount")));
        row(out, "正确次数", cell(statistics.path("correctCount")));
        row(out, "正确率", percent(statistics.path("accuracy")));
        row(out, "去重题数", cell(statistics.path("uniqueQuestions")));
        row(out, "当前错题标记（不按作答日期筛选）", cell(statistics.path("wrongCount")));
        row(out, "学习时长", "未记录");
        out.append("\n### 每日有效作答\n\n| 上海日期 | 作答 | 正确 |\n| --- | --- | --- |\n");
        for (JsonNode day : statistics.path("daily")) row(out, cell(day.path("statDate")), cell(day.path("questionCount")), cell(day.path("correctCount")));
        if (statistics.path("questionCount").asInt() == 0) out.append("\n暂无有效作答，正确率及薄弱点暂无法判断。\n");
        out.append("\n### 知识点统计\n\n| 知识点 | 作答 | 正确 | 样本提示 |\n| --- | --- | --- | --- |\n");
        for (JsonNode point : statistics.path("knowledgePoints")) row(out, cell(point.path("knowledgePoint")), cell(point.path("questionCount")),
                cell(point.path("correctCount")), point.path("sampleInsufficient").asBoolean() ? "样本不足" : "仅反映区间作答");
        LearningProfiles profileService = profiles.getIfAvailable();
        JsonNode profile = profileService == null ? json.nullNode() : json.valueToTree(profileService.profile(owner));
        String version = "规则报告 " + statistics.path("from").asText() + "—" + statistics.path("to").asText();
        out.append("\n## 学情画像与复习建议\n\n");
        if (profile.isNull()) out.append("学情画像功能尚未启用；以上仅为有效作答统计。\n\n");
        else {
            version += " · 画像 v" + profile.path("revision").asInt();
            out.append("画像更新时间：").append(cell(profile.path("updatedAt"))).append("；算法 ").append(cell(profile.path("algorithmVersion")))
                    .append("；蓝图 ").append(cell(profile.path("blueprintVersion"))).append("。画像是独立快照，不限于上面的30天区间。\n\n");
            out.append("| 画像指标 | 数值 |\n| --- | --- |\n");
            row(out, "独立样本", cell(profile.path("independentSamples")));
            row(out, "辅助样本", cell(profile.path("assistedSamples")));
            row(out, "未知样本", cell(profile.path("unknownSamples")));
            row(out, "蓝图覆盖", percent(profile.path("coverage")));
            row(out, "408实验性参考分（未经整卷校准）", profile.path("referenceScore").isNumber() ? cell(profile.get("referenceScore")) : "证据不足");
            strings(out, profile.path("notices"), "提示：");
            out.append("\n掌握指数反映现有证据；辅助与未知作答不视为独立掌握。无样本不等于不会，参考分不能用于预测录取概率。\n\n");
            out.append("| 科目／知识点／难度 | 独立 | 正确 | 辅助 | 未知 | 掌握指数 | 复习建议 |\n| --- | --- | --- | --- | --- | --- | --- |\n");
            for (JsonNode group : profile.path("groups")) row(out,
                    cell(group.path("subject")) + "／" + cell(group.path("knowledgePoint")) + "／" + cell(group.path("difficulty")),
                    cell(group.path("samples")), cell(group.path("correct")), cell(group.path("assisted")), cell(group.path("unknown")),
                    percent(group.path("masteryIndex")), advice(group));
            if (profile.path("groups").isEmpty()) out.append("\n尚未建立知识点画像，可先完成一次诊断或练习。\n");
        }
        return new Content("学习情况分析报告", version, out.toString(), charts.learning(statistics, profile));
    }

    private static String advice(JsonNode group) {
        if (group.path("samples").asInt() < 5 || !group.path("masteryIndex").isNumber()) return "样本不足，先补充独立练习";
        if (group.path("anomaly").asBoolean()) return "证据异常，先核对作答记录";
        return group.path("masteryIndex").asDouble() < 0.6 ? "优先复习概念并独立练习" : "间隔复习并继续验证";
    }
    private static void plan(StringBuilder out, JsonNode plan) {
        out.append("\n## 复习安排\n\n建议可调整，未自动创建练习或保存笔记。\n\n");
        strings(out, plan.path("basis"), "依据：");
        for (JsonNode day : plan.path("days")) {
            out.append("\n### 第 ").append(day.path("day").asInt()).append(" 天 · ").append(cell(day.path("topic"))).append("\n\n");
            strings(out, day.path("tasks"), "");
        }
    }
    private static void catalog(StringBuilder out, JsonNode catalog) {
        out.append("\n## ").append(cell(catalog.path("school").path("name"))).append(" · 库内信息\n\n")
                .append(cell(catalog.path("school").path("province"))).append(" · ")
                .append(cell(catalog.path("school").path("level"))).append("\n\n")
                .append("查询年份：").append(cell(catalog.path("targetYear")))
                .append("；已有年份：").append(join(catalog.path("availableYears")))
                .append("；匹配专业 ").append(cell(catalog.path("total"))).append(" 条。\n\n")
                .append("采集待核实资料不代表已完成官方核验。\n\n");
        if (catalog.path("details").isEmpty()) out.append("库内暂无符合本次条件的专业记录，未使用其他年份替代。\n\n");
        for (JsonNode warning : catalog.path("warnings")) out.append("提示：").append(cell(warning.path("message"))).append("\n\n");
        for (JsonNode row : catalog.path("details")) {
            out.append("### ").append(cell(row.path("year"))).append("年 · ").append(cell(row.path("majorName")))
                    .append("（").append(cell(row.path("majorCode"))).append("）\n\n");
            JsonNode context = row.path("admissionMetrics");
            if (context.isObject()) out.append(cell(context.path("college"))).append(" · ")
                    .append(cell(context.path("track"))).append("\n\n");
            catalogMetric(out, context.path("enrollment"), "招生计划", row.path("enrollmentCount"), row.path("year"));
            catalogMetric(out, context.path("cutoffReference"), "复试参考线", row.path("scoreLine"), row.path("year"));
            if (row.hasNonNull("remark")) out.append("原登记备注：").append(cell(row.path("remark"))).append("\n\n");
        }
    }

    private static void catalogMetric(StringBuilder out, JsonNode metric, String label, JsonNode legacy, JsonNode year) {
        if (!metric.isObject()) {
            out.append(label).append("：").append(legacy.isNumber() ? cell(year) + "年原登记 " + cell(legacy) : "未收录或未通过校验")
                    .append("\n\n");
            return;
        }
        String status = metric.path("status").asText();
        String state = switch (status) {
            case "OFFICIAL" -> "官方来源"; case "UNVERIFIED" -> "第三方·待核实";
            case "NOT_PUBLISHED" -> "未公布"; case "SCOPE_MISMATCH" -> "范围不匹配";
            case "CONFLICT" -> "来源冲突"; default -> "未找到可靠来源";
        };
        out.append(cell(metric.path("year"))).append("年 ").append(label).append("：")
                .append(metric.path("value").isNumber() ? cell(metric.path("value")) + (label.equals("招生计划") ? "人" : "分") : state)
                .append(" · ").append(state).append("\n\n");
        String basis = switch (metric.path("basis").asText()) {
            case "ORDINARY_EXAM" -> "统考计划";
            case "TOTAL_INCLUDING_RECOMMENDED" -> "招生总计划（含推免）";
            case "TOTAL_UNSPECIFIED" -> "招生总计划（是否含推免未说明）";
            default -> "";
        };
        out.append(basis).append(" · ").append(cell(metric.path("scopeLabel"))).append("\n\n");
        if (metric.hasNonNull("notice")) out.append(cell(metric.path("notice"))).append("\n\n");
        for (JsonNode source : metric.path("sources")) {
            out.append("- 来源：").append(cell(source.path("title"))).append(" · ").append(cell(source.path("url")))
                    .append(" · ").append(cell(source.path("locator"))).append(" · 获取于 ")
                    .append(cell(source.path("retrievedAt"))).append("\n");
        }
        out.append("\n");
    }

    private static void append(StringBuilder out, JsonNode value) {
        if (value.isValueNode() && !value.isNull() && !value.asText().isBlank()) out.append(value.asText()).append("\n\n");
    }
    private static void strings(StringBuilder out, JsonNode values, String prefix) {
        for (JsonNode value : values) if (value.isTextual()) out.append("- ").append(prefix).append(cell(value)).append("\n");
        out.append("\n");
    }
    private static String join(JsonNode values) {
        var parts = new ArrayList<String>();
        for (JsonNode value : values) if (value.isValueNode()) parts.add(cell(value));
        return String.join("、", parts);
    }
    private static String percent(JsonNode value) { return value.isNumber() ? String.format(java.util.Locale.ROOT, "%.1f%%", value.asDouble() * 100) : "证据不足"; }
    private static String cell(JsonNode value) { return value.isMissingNode() || value.isNull() ? "未记录" : escape(value.asText()); }
    private static String cell(Object value) { return value == null ? "未记录" : escape(String.valueOf(value)); }
    private static String escape(String text) { return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ").replace("<", "＜").replace(">", "＞"); }
    private static void row(StringBuilder out, String... cells) { out.append("| ").append(String.join(" | ", cells)).append(" |\n"); }
}
