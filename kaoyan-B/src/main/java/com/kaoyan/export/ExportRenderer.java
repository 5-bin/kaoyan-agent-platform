package com.kaoyan.export;

import com.openhtmltopdf.pdfboxout.PdfRendererBuilder;
import com.openhtmltopdf.outputdevice.helper.ExternalResourceControlPriority;
import org.apache.poi.util.Units;
import org.apache.poi.xwpf.usermodel.*;
import org.commonmark.ext.gfm.tables.*;
import org.commonmark.node.*;
import org.commonmark.parser.Parser;
import org.commonmark.renderer.html.HtmlRenderer;
import org.commonmark.renderer.html.HtmlNodeRendererContext;
import org.commonmark.renderer.NodeRenderer;
import org.springframework.stereotype.Component;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Set;
import static com.kaoyan.export.ExportContracts.*;

/** Three deterministic renderers share a CommonMark tree; untrusted HTML and remote assets never execute. */
@Component
public class ExportRenderer {
    private static final String FONT = "Noto Sans SC";
    private static final List<org.commonmark.Extension> EXTENSIONS = List.of(TablesExtension.create());

    /** Normalizes the saved snapshot so even downloaded Markdown has no active HTML or remote images. */
    public String canonicalMarkdown(String input) {
        Node tree = Parser.builder().extensions(EXTENSIONS).build().parse(input);
        sanitize(tree);
        return org.commonmark.renderer.markdown.MarkdownRenderer.builder().extensions(EXTENSIONS).build().render(tree);
    }

    private static void sanitize(Node parent) {
        for (Node node = parent.getFirstChild(); node != null;) {
            Node next = node.getNext();
            if (node instanceof Image) {
                node.insertBefore(new Text("[图片说明：" + plain(node) + "]")); node.unlink();
            } else if (node instanceof HtmlInline html) {
                node.insertBefore(new Text(html.getLiteral())); node.unlink();
            } else if (node instanceof HtmlBlock html) {
                Paragraph paragraph = new Paragraph(); paragraph.appendChild(new Text(html.getLiteral()));
                node.insertBefore(paragraph); node.unlink();
            } else if (node instanceof Link link && !safeLink(link.getDestination())) {
                node.insertBefore(new Text(plain(node))); node.unlink();
            } else sanitize(node);
            node = next;
        }
    }

    public byte[] render(Preview report, String format) throws IOException {
        if (format == null || !Set.of("md", "docx", "pdf").contains(format)) throw new IllegalArgumentException("未知导出格式");
        for (Chart chart : report.charts()) if (!chart.png().matches("data:image/png;base64,[A-Za-z0-9+/=]+"))
            throw new IOException("图表格式无效");
        if (format.equals("md")) return report.markdown().getBytes(StandardCharsets.UTF_8);
        Node tree = Parser.builder().extensions(EXTENSIONS).build().parse(report.markdown());
        if (format.equals("docx")) return word(report, tree);
        return pdf(report, tree);
    }

    private byte[] pdf(Preview report, Node tree) throws IOException {
        wrapTree(tree);
        String html = HtmlRenderer.builder().extensions(EXTENSIONS).escapeHtml(true).softbreak("<br />\n")
                .sanitizeUrls(true).urlSanitizer(new org.commonmark.renderer.html.UrlSanitizer() {
                    @Override public String sanitizeLinkUrl(String url) { return safeLink(url) ? url : ""; }
                    @Override public String sanitizeImageUrl(String url) { return ""; }
                })
                .nodeRendererFactory(ImageDescription::new).build().render(tree);
        StringBuilder body = new StringBuilder(html);
        Set<String> assets = report.charts().stream().map(Chart::png).collect(java.util.stream.Collectors.toSet());
        for (Chart chart : report.charts()) body.append("<div class=\"figure\"><h2>").append(xml(chart.title()))
                .append("</h2><img alt=\"").append(xml(chart.title())).append("\" src=\"").append(chart.png()).append("\" /></div>");
        String document = """
                <!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><head><meta charset="UTF-8" />
                <style>
                @page { size: A4; margin: 20mm 18mm; @bottom-center { content: counter(page); font-size: 9pt; } }
                body { font-family: 'Noto Sans SC'; color: #192332; font-size: 10pt; line-height: 1.65; }
                h1,h2,h3,h4,h5,h6 { color: #000; line-height: 1.4; page-break-after: avoid; }
                h1 { font-size: 22pt; margin: 0 0 16pt; } h2 { font-size: 15pt; margin-top: 18pt; }
                h3 { font-size: 12pt; } p { margin: 7pt 0; } a { color: #244d82; }
                table { width: 100%; border-collapse: collapse; margin: 10pt 0; -fs-table-paginate: paginate; table-layout: fixed; }
                th,td { border: 0.5pt solid #d9d9d9; padding: 5pt; vertical-align: middle; word-wrap: break-word; }
                th { background: #edf2f7; color: #000; } tr { page-break-inside: avoid; }
                pre { white-space: pre-wrap; word-wrap: break-word; background: #f3f5f7; padding: 8pt; }
                code { font-family: 'Noto Sans SC'; font-size: 9pt; } blockquote { margin-left: 14pt; color: #48566a; }
                .figure { page-break-inside: avoid; } img { width: 100%; height: auto; }
                </style></head><body>
                """ + body + "</body></html>";
        try (var output = new ByteArrayOutputStream()) {
            PdfRendererBuilder builder = new PdfRendererBuilder();
            builder.useFastMode();
            builder.useFont(() -> ExportRenderer.class.getResourceAsStream("/export-fonts/NotoSansSC-Regular.ttf"), FONT);
            builder.useExternalResourceAccessControl((url, type) -> assets.contains(url), ExternalResourceControlPriority.RUN_BEFORE_RESOLVING_URI);
            builder.useExternalResourceAccessControl((url, type) -> assets.contains(url), ExternalResourceControlPriority.RUN_AFTER_RESOLVING_URI);
            builder.withHtmlContent(document, null).toStream(output).run();
            return output.toByteArray();
        }
    }

    private byte[] word(Preview report, Node tree) throws IOException {
        try (XWPFDocument document = new XWPFDocument(); var output = new ByteArrayOutputStream()) {
            var section = document.getDocument().getBody().addNewSectPr();
            var size = section.addNewPgSz(); size.setW(java.math.BigInteger.valueOf(11906)); size.setH(java.math.BigInteger.valueOf(16838));
            var margin = section.addNewPgMar();
            margin.setTop(java.math.BigInteger.valueOf(1134)); margin.setBottom(java.math.BigInteger.valueOf(1134));
            margin.setLeft(java.math.BigInteger.valueOf(1020)); margin.setRight(java.math.BigInteger.valueOf(1020));
            document.createStyles();
            for (String id : List.of("Title", "Heading1", "Heading2", "Heading3")) {
                var ct = org.openxmlformats.schemas.wordprocessingml.x2006.main.CTStyle.Factory.newInstance();
                ct.setStyleId(id); ct.addNewName().setVal(id);
                var rpr = ct.addNewRPr(); rpr.addNewColor().setVal("000000"); rpr.addNewRFonts().setAscii(FONT);
                rpr.getRFontsArray(0).setEastAsia(FONT);
                document.getStyles().addStyle(new XWPFStyle(ct));
            }
            blocks(document, tree, 0, "");
            for (Chart chart : report.charts()) {
                XWPFParagraph heading = paragraph(document, 0); heading.setKeepNext(true);
                text(heading, chart.title(), true, false, 14);
                XWPFRun run = paragraph(document, 0).createRun();
                byte[] png = Base64.getDecoder().decode(chart.png().substring("data:image/png;base64,".length()));
                var image = javax.imageio.ImageIO.read(new ByteArrayInputStream(png));
                if (image == null) throw new IOException("图表格式无效");
                try {
                    run.addPicture(new ByteArrayInputStream(png), org.apache.poi.xwpf.usermodel.Document.PICTURE_TYPE_PNG, chart.title(),
                            Units.toEMU(490), Units.toEMU(490.0 * image.getHeight() / image.getWidth()));
                } catch (org.apache.poi.openxml4j.exceptions.InvalidFormatException e) { throw new IOException("图表格式无效", e); }
            }
            embedFont(document);
            document.write(output);
            return output.toByteArray();
        }
    }

    private static void embedFont(XWPFDocument document) throws IOException {
        // OOXML font obfuscation is specified by ECMA-376, not encryption. The
        // bundled OFL font explicitly permits embedding and redistribution.
        String key = "00112233-4455-6677-8899-AABBCCDDEEFF";
        byte[] font;
        try (var input = ExportRenderer.class.getResourceAsStream("/export-fonts/NotoSansSC-Regular.ttf")) {
            if (input == null) throw new IOException("导出字体缺失");
            font = input.readAllBytes();
        }
        byte[] guid = java.util.HexFormat.of().parseHex(key.replace("-", ""));
        for (int i = 0; i < 32; i++) font[i] ^= guid[15 - i % 16];
        try {
            var pack = document.getPackage();
            var fontPart = pack.createPart(org.apache.poi.openxml4j.opc.PackagingURIHelper.createPartName("/word/fonts/ExportSans.odttf"),
                    "application/vnd.openxmlformats-officedocument.obfuscatedFont");
            try (var stream = fontPart.getOutputStream()) { stream.write(font); }
            var tablePart = pack.createPart(org.apache.poi.openxml4j.opc.PackagingURIHelper.createPartName("/word/fontTable.xml"),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml");
            String relation = tablePart.addRelationship(fontPart.getPartName(), org.apache.poi.openxml4j.opc.TargetMode.INTERNAL,
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font").getId();
            String xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><w:fonts xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
                    + "<w:font w:name=\"" + FONT + "\"><w:family w:val=\"swiss\"/><w:embedRegular r:id=\"" + relation + "\" w:fontKey=\"{" + key + "}\"/></w:font></w:fonts>";
            try (var stream = tablePart.getOutputStream()) { stream.write(xml.getBytes(StandardCharsets.UTF_8)); }
            document.getPackagePart().addRelationship(tablePart.getPartName(), org.apache.poi.openxml4j.opc.TargetMode.INTERNAL,
                    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable");
            document.getSettings().getCTSettings().addNewEmbedTrueTypeFonts();
        } catch (org.apache.poi.openxml4j.exceptions.InvalidFormatException e) { throw new IOException("字体封装失败", e); }
    }

    private void blocks(XWPFDocument document, Node parent, int indent, String prefix) {
        for (Node node = parent.getFirstChild(); node != null; node = node.getNext()) {
            if (node instanceof Heading heading) {
                XWPFParagraph p = paragraph(document, indent); p.setKeepNext(true);
                p.setStyle(heading.getLevel() == 1 ? "Title" : "Heading" + Math.min(3, heading.getLevel() - 1));
                inline(p, node, true, false, heading.getLevel() == 1 ? 22 : Math.max(11, 18 - heading.getLevel() * 2));
            } else if (node instanceof Paragraph) {
                XWPFParagraph p = paragraph(document, indent);
                if (!prefix.isEmpty()) text(p, prefix, false, false, 11);
                inline(p, node, false, false, 11);
                prefix = "";
            } else if (node instanceof BulletList || node instanceof OrderedList) {
                int number = node instanceof OrderedList ordered ? ordered.getMarkerStartNumber() : 1;
                for (Node item = node.getFirstChild(); item != null; item = item.getNext())
                    blocks(document, item, indent + 1, node instanceof OrderedList ? number++ + ". " : "• ");
            } else if (node instanceof BlockQuote) {
                blocks(document, node, indent + 1, "引用：");
            } else if (node instanceof FencedCodeBlock code) code(document, code.getLiteral(), indent);
            else if (node instanceof IndentedCodeBlock code) code(document, code.getLiteral(), indent);
            else if (node instanceof HtmlBlock raw) code(document, raw.getLiteral(), indent);
            else if (node instanceof TableBlock) table(document, node);
            else if (node instanceof ThematicBreak) text(paragraph(document, indent), "* * *", false, false, 11);
            else blocks(document, node, indent, prefix);
        }
    }

    private void code(XWPFDocument document, String literal, int indent) {
        // One paragraph per line allows very long code blocks to split across pages.
        for (String line : literal.split("\n", -1)) {
            XWPFParagraph p = paragraph(document, indent); p.setSpacingAfter(0);
            p.getCTP().addNewPPr().addNewShd().setFill("F3F5F7");
            text(p, line.isEmpty() ? " " : line, false, false, 9);
        }
    }

    private void table(XWPFDocument document, Node table) {
        List<Node> rows = new ArrayList<>();
        for (Node section = table.getFirstChild(); section != null; section = section.getNext())
            for (Node row = section.getFirstChild(); row != null; row = row.getNext()) rows.add(row);
        if (rows.isEmpty()) return;
        int columns = 0;
        for (Node cell = rows.get(0).getFirstChild(); cell != null; cell = cell.getNext()) columns++;
        if (columns == 0) return;
        XWPFTable output = document.createTable(rows.size(), columns);
        output.setWidth("100%"); output.setCellMargins(70, 80, 70, 80);
        for (XWPFTable.XWPFBorderType border : List.of(XWPFTable.XWPFBorderType.SINGLE)) {
            output.setTopBorder(border, 4, 0, "D9D9D9"); output.setBottomBorder(border, 4, 0, "D9D9D9");
            output.setLeftBorder(border, 4, 0, "D9D9D9"); output.setRightBorder(border, 4, 0, "D9D9D9");
            output.setInsideHBorder(border, 4, 0, "D9D9D9"); output.setInsideVBorder(border, 4, 0, "D9D9D9");
        }
        var layout = output.getCTTbl().getTblPr().addNewTblLayout();
        layout.setType(org.openxmlformats.schemas.wordprocessingml.x2006.main.STTblLayoutType.FIXED);
        for (int i = 0; i < rows.size(); i++) {
            XWPFTableRow row = output.getRow(i);
            row.setRepeatHeader(i == 0);
            int column = 0;
            for (Node cell = rows.get(i).getFirstChild(); cell != null && column < columns; cell = cell.getNext()) {
                XWPFTableCell target = row.getCell(column++);
                target.setWidth(Integer.toString(9866 / columns)); target.setVerticalAlignment(XWPFTableCell.XWPFVertAlign.CENTER);
                if (i == 0) target.setColor("EDF2F7");
                XWPFParagraph p = target.getParagraphs().get(0); p.setSpacingAfter(40);
                inline(p, cell, i == 0, false, columns > 5 ? 9 : 10);
            }
        }
        paragraph(document, 0);
    }

    private static XWPFParagraph paragraph(XWPFDocument document, int indent) {
        XWPFParagraph p = document.createParagraph(); p.setSpacingAfter(100); p.setSpacingBetween(1.4);
        p.setIndentationLeft(indent * 260);
        return p;
    }
    private static void inline(XWPFParagraph p, Node parent, boolean bold, boolean italic, int size) {
        for (Node node = parent.getFirstChild(); node != null; node = node.getNext()) {
            if (node instanceof Text value) text(p, value.getLiteral(), bold, italic, size);
            else if (node instanceof Code value) text(p, value.getLiteral(), bold, italic, size);
            else if (node instanceof HtmlInline raw) text(p, raw.getLiteral(), bold, italic, size);
            else if (node instanceof SoftLineBreak || node instanceof HardLineBreak) p.createRun().addBreak();
            else if (node instanceof Image) { text(p, "[图片说明：" + plain(node) + "]", bold, italic, size); }
            else if (node instanceof Link link && safeLink(link.getDestination())) {
                XWPFHyperlinkRun run = p.createHyperlinkRun(link.getDestination()); configure(run, bold, italic, size); run.setText(breakable(plain(node))); run.setColor("244D82");
            } else inline(p, node, bold || node instanceof StrongEmphasis, italic || node instanceof Emphasis, size);
        }
    }
    private static void text(XWPFParagraph p, String text, boolean bold, boolean italic, int size) {
        XWPFRun run = p.createRun(); configure(run, bold, italic, size); run.setText(breakable(text));
    }
    private static void configure(XWPFRun run, boolean bold, boolean italic, int size) {
        run.setFontFamily(FONT); run.setFontFamily(FONT, XWPFRun.FontCharRange.eastAsia);
        run.setFontSize(size); run.setBold(bold); run.setItalic(italic); run.setColor("000000");
    }
    private static String plain(Node parent) {
        StringBuilder result = new StringBuilder();
        for (Node node = parent.getFirstChild(); node != null; node = node.getNext()) {
            if (node instanceof Text text) result.append(text.getLiteral());
            else if (node instanceof Code text) result.append(text.getLiteral());
            else result.append(plain(node));
        }
        return result.toString();
    }
    private static boolean safeLink(String value) {
        try { URI uri = URI.create(value); return "https".equalsIgnoreCase(uri.getScheme()) && uri.getHost() != null && uri.getUserInfo() == null; }
        catch (IllegalArgumentException e) { return false; }
    }
    private static String breakable(String value) {
        // Chinese already has legal line-break opportunities. Only break exceptional
        // long ASCII tokens, preserving ordinary words and Chinese search/copy text.
        var matcher = java.util.regex.Pattern.compile("[!-~]{81,}").matcher(value);
        return matcher.replaceAll(match -> java.util.regex.Matcher.quoteReplacement(
                match.group().replaceAll("(.{32})(?=.)", "$1\u200B")));
    }
    private static void wrapTree(Node parent) {
        for (Node node = parent.getFirstChild(); node != null; node = node.getNext()) {
            if (node instanceof Text text) text.setLiteral(breakable(text.getLiteral()));
            else if (node instanceof Code code) code.setLiteral(breakable(code.getLiteral()));
            else if (node instanceof FencedCodeBlock code) code.setLiteral(breakable(code.getLiteral()));
            else if (node instanceof IndentedCodeBlock code) code.setLiteral(breakable(code.getLiteral()));
            wrapTree(node);
        }
    }
    private static String xml(String value) { return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;"); }
    private static final class ImageDescription implements NodeRenderer {
        private final HtmlNodeRendererContext context;
        private ImageDescription(HtmlNodeRendererContext context) { this.context = context; }
        @Override public Set<Class<? extends Node>> getNodeTypes() { return Set.of(Image.class); }
        @Override public void render(Node node) { context.getWriter().text("[图片说明：" + plain(node) + "]"); }
    }
}
