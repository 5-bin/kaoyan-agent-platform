package com.kaoyan.export;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.stereotype.Component;
import javax.imageio.ImageIO;
import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import static com.kaoyan.export.ExportContracts.Chart;

/** Local deterministic charts; no browser screenshots, remote assets or model output. */
@Component
public class ExportCharts {
    private final Font font;
    public ExportCharts() {
        try (var input = ExportCharts.class.getResourceAsStream("/export-fonts/NotoSansSC-Regular.ttf")) {
            if (input == null) throw new IllegalStateException("导出中文字体缺失");
            font = Font.createFont(Font.TRUETYPE_FONT, input);
        } catch (java.awt.FontFormatException | IOException e) { throw new IllegalStateException("导出字体无法加载", e); }
    }

    public List<Chart> learning(JsonNode stats, JsonNode profile) {
        List<Chart> results = new ArrayList<>();
        List<String> labels = new ArrayList<>();
        List<Double> values = new ArrayList<>();
        java.time.LocalDate from = java.time.LocalDate.parse(stats.path("from").asText());
        for (int day = 0; day < 30; day++) {
            String date = from.plusDays(day).toString();
            labels.add(date.substring(5));
            double count = 0;
            for (JsonNode item : stats.path("daily")) if (date.equals(item.path("statDate").asText())) count = item.path("questionCount").asDouble();
            values.add(count);
        }
        results.add(draw("近30天有效作答趋势（次数）", labels, values, true));
        labels.clear(); values.clear();
        for (JsonNode point : stats.path("knowledgePoints")) {
            labels.add(point.path("knowledgePoint").asText()); values.add(point.path("questionCount").asDouble());
            if (labels.size() == 12) break;
        }
        if (!labels.isEmpty()) results.add(draw("知识点作答分布（前12项；完整数据见表）", labels, values, false));
        if (!profile.isNull()) {
            labels = List.of("独立样本", "辅助样本", "未知样本");
            values = List.of(profile.path("independentSamples").asDouble(), profile.path("assistedSamples").asDouble(), profile.path("unknownSamples").asDouble());
            results.add(draw("画像证据组成（画像独立快照）", labels, values, false));
        }
        return List.copyOf(results);
    }

    private Chart draw(String title, List<String> labels, List<Double> values, boolean line) {
        int width = 1200, height = line ? 420 : Math.max(280, 90 + labels.size() * 40);
        BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = image.createGraphics();
        try {
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            g.setColor(Color.WHITE); g.fillRect(0, 0, width, height);
            // The accessible figure caption in preview/Word/PDF supplies the title.
            g.setColor(new Color(25, 35, 50));
            g.setFont(font.deriveFont(19f));
            double max = Math.max(1, values.stream().mapToDouble(Double::doubleValue).max().orElse(1));
            if (line) {
                int bottom = height - 50;
                g.setColor(new Color(210, 218, 228)); g.drawLine(70, 70, 70, bottom); g.drawLine(70, bottom, width - 45, bottom);
                for (int i = 0; i <= 4; i++) {
                    int y = bottom - i * (bottom - 80) / 4;
                    g.drawString(String.format(java.util.Locale.ROOT, "%.0f", max * i / 4), 16, y + 5);
                }
                int lastX = 0, lastY = 0;
                for (int i = 0; i < values.size(); i++) {
                    int x = 80 + i * (width - 145) / Math.max(1, values.size() - 1);
                    int y = bottom - (int) (values.get(i) / max * (bottom - 80));
                    g.setColor(new Color(45, 95, 180));
                    if (i > 0) g.drawLine(lastX, lastY, x, y);
                    g.fillOval(x - 4, y - 4, 8, 8);
                    if (i % 5 == 0 || i == values.size() - 1) { g.setColor(Color.DARK_GRAY); g.drawString(labels.get(i), x - 25, height - 16); }
                    lastX = x; lastY = y;
                }
            } else {
                for (int i = 0; i < labels.size(); i++) {
                    int y = 70 + i * 40;
                    g.setColor(Color.DARK_GRAY);
                    String label = labels.get(i);
                    if (label.length() > 18) label = label.substring(0, 17) + "…";
                    g.drawString(label, 28, y + 20);
                    int barWidth = (int) (values.get(i) / max * 660);
                    g.setColor(new Color(66, 111, 181)); g.fillRoundRect(395, y, barWidth, 26, 6, 6);
                    g.setColor(Color.DARK_GRAY); g.drawString(Integer.toString(values.get(i).intValue()), 410 + barWidth, y + 21);
                }
            }
            try (var output = new ByteArrayOutputStream()) {
                ImageIO.write(image, "png", output);
                return new Chart(title, "data:image/png;base64," + Base64.getEncoder().encodeToString(output.toByteArray()));
            }
        } catch (IOException e) { throw new IllegalStateException("导出图表生成失败", e); }
        finally { g.dispose(); }
    }
}
