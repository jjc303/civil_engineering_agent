import os
from pathlib import Path

import pytest

from agent.services.report_pdf import write_windows_report


@pytest.mark.skipif(os.name != "nt", reason="uses Windows Chinese font")
def test_windows_report_preserves_chinese_statistics_and_multiline_content(tmp_path: Path):
    from pypdf import PdfReader
    target = tmp_path / "report.pdf"
    write_windows_report(target, start="2026-10-10 19:03", end="2026-10-10 19:05",
        stats={"total": 3, "repeat_occurrences": 1, "by_type": {"NO_HELMET": 3}},
        content={"summary": "本次检测记录共三起。", "risk_analysis": "第一行\n第二行 & <风险>", "remediation": "核查安全帽佩戴。"},
        citations=[{"title": "施工安全规范", "page_or_section": "第 3 页"}])
    text = "\n".join(page.extract_text() for page in PdfReader(target).pages)
    assert "未规范佩戴安全帽" in text
    assert "有效违规事件：3" in text
    assert "第二行 & <风险>" in text
    assert "第 3 页" in text
