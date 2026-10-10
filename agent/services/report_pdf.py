"""PDF export on Windows without requiring a separate GTK installation."""
from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from xml.sax.saxutils import escape

_font_lock = Lock()
_RISK_LABELS = {
    "NO_HELMET": "未规范佩戴安全帽",
    "DANGER_ZONE_INTRUSION": "危险区域进入",
    "DWELL_TIMEOUT": "危险区域停留超时",
}


def write_windows_report(path: Path, *, start: str, end: str, stats: dict, content: dict, citations: list) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    font = "CivilSafetyChinese"
    with _font_lock:
        if font not in pdfmetrics.getRegisteredFontNames():
            font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/simsun.ttc"
            if not font_path.is_file():
                raise RuntimeError("Chinese PDF font is missing")
            pdfmetrics.registerFont(TTFont(font, str(font_path), subfontIndex=0))
    body = ParagraphStyle("body", fontName=font, fontSize=10, leading=17, wordWrap="CJK", spaceAfter=9, textColor=colors.HexColor("#303246"))
    heading = ParagraphStyle("heading", parent=body, fontSize=13, leading=20, spaceBefore=14, spaceAfter=8, textColor=colors.HexColor("#685790"), keepWithNext=True)
    title = ParagraphStyle("title", parent=heading, fontSize=21, leading=30, alignment=TA_CENTER, spaceAfter=18)
    citation_note = ParagraphStyle("citation_note", parent=body, keepWithNext=True)
    def paragraph(value: object, style=body):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), style)

    source = os.getenv("REPORT_SOURCE_LABEL", "").strip()
    story = [paragraph("施工安全报告", title), paragraph(f"统计期间：{start} - {end}")]
    if source:
        story.append(paragraph("数据来源：" + source))
    story.extend([paragraph("统计概况", heading),
        paragraph(f"有效违规事件：{stats['total']}；重复出现次数：{stats['repeat_occurrences']}"),
        paragraph("重复口径：同一摄像头、区域、违规类型在统计期间内再次出现；不代表同一人员重复违规。误报已排除。")])
    rows = [[paragraph("风险类型"), paragraph("次数")]]
    rows.extend([[paragraph(_RISK_LABELS.get(name, name)), paragraph(count)] for name, count in stats["by_type"].items()])
    table = Table(rows, colWidths=[136 * mm, 35 * mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0eafa")),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#e2d9ed")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([table, Spacer(1, 4 * mm)])
    for label, key in [("总结", "summary"), ("风险分析", "risk_analysis"), ("整改建议", "remediation")]:
        story.extend([paragraph(label, heading), paragraph(content[key])])
    story.append(paragraph("规范资料", heading))
    if citations:
        story.append(paragraph("资料版本有效性须核实；引用页码对应已入库的原文。", citation_note))
        story.extend(paragraph(f"{index}. {item['title']} · {item['page_or_section']}") for index, item in enumerate(citations, 1))
    else:
        story.append(paragraph("当前规范库未检索到可引用依据。"))
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont(font, 9)
        canvas.setFillColor(colors.HexColor("#918899"))
        canvas.drawCentredString(A4[0] / 2, 12 * mm, f"第 {document.page} 页")
        canvas.restoreState()
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm, title="施工安全报告").build(story, onFirstPage=footer, onLaterPages=footer)
