from types import SimpleNamespace

from agent.rag.manager import _pdf_text


def test_broken_pdf_font_characters_remain_explicit_and_utf8_safe():
    page = SimpleNamespace(extract_text=lambda: "安全帽\udcff规定")
    text = _pdf_text(page)
    assert text == "安全帽\ufffd规定"
    assert text.encode("utf-8").decode("utf-8") == text


def test_image_only_pdf_does_not_gain_invented_text():
    assert _pdf_text(SimpleNamespace(extract_text=lambda: None)) == ""
