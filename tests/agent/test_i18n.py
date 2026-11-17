from __future__ import annotations

from fastapi.testclient import TestClient

from agent.contracts.chat import ChatRequest
from agent.core.config import Settings
from agent.domain.standards_guard import contains_unsupported_standard_reference
from agent.domain.violation_catalog import SEVERITY_LABELS, VIOLATION_LABELS
from agent.i18n import (
    localize_response,
    localize_text,
    parse_accept_language,
    resolve_request_locale,
    to_simplified_text,
)
from agent.main import create_app


def _make_settings() -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="i18n-test-token",
        llm_provider="fake",
        auto_create_schema=True,
    )


def test_accept_language_parsing_and_query_override() -> None:
    assert parse_accept_language(None) == "zh-CN"
    assert parse_accept_language("en-US,en;q=0.9") == "zh-CN"
    assert parse_accept_language("zh-HK,zh-TW;q=0.9,zh-CN;q=0.8") == "zh-HK"
    assert parse_accept_language("zh-MO") == "zh-HK"
    assert parse_accept_language("zh-Hant-HK") == "zh-HK"
    assert parse_accept_language("zh-CN,zh-HK;q=0.8") == "zh-CN"
    assert resolve_request_locale("zh-CN", "zh-HK") == "zh-HK"
    assert resolve_request_locale("zh-HK", "zh-CN") == "zh-CN"


def test_converter_preserves_code_spans_urls_and_standard_codes() -> None:
    raw = (
        "依据《建筑施工安全检查标准》JGJ 59-2011，"
        "请核对 `cam_field_01` 与 `/api/v1/violations`，"
        "详情见 https://example.com/safety?mode=违规。\n"
        "```json\n{\"status\": \"未佩戴安全帽\"}\n```"
    )
    hk = localize_text(raw, "zh-HK")
    assert "依據《建築施工安全檢查標準》JGJ 59-2011" in hk
    assert "`cam_field_01`" in hk
    assert "`/api/v1/violations`" in hk
    assert "https://example.com/safety?mode=违规" in hk
    assert '{"status": "未佩戴安全帽"}' in hk
    assert to_simplified_text("依據《建築施工安全檢查標準》") == "依据《建筑施工安全检查标准》"


def test_standards_guard_accepts_traditional_citation_against_simplified_evidence() -> None:
    evidence = "来源：《建筑施工安全检查标准》JGJ 59-2011；章节：第 3.1.3 条\n高风险区域严禁人员长时间滞留。"
    answer_hk = "依據《建築施工安全檢查標準》JGJ 59-2011 第 3.1.3 條規定，高風險區域嚴禁長時間滯留。"
    assert contains_unsupported_standard_reference(answer_hk, evidence) is False


def test_localize_response_skips_machine_identifiers_and_is_non_mutating() -> None:
    original = {
        "camera_id": "摄像头编号-保留",
        "violation_type": "NO_HELMET",
        "severity": "CRITICAL",
        "summary": "发现未佩戴安全帽违规事件",
    }
    localized = localize_response(original, "zh-HK")
    assert localized["camera_id"] == "摄像头编号-保留"
    assert localized["violation_type"] == "NO_HELMET"
    assert localized["summary"] == "發現未佩戴安全帽違規事件"
    # Canonical original dictionary remains unchanged
    assert original["summary"] == "发现未佩戴安全帽违规事件"


def test_meta_and_ui_config_and_heatmap_respect_accept_language_without_cache_pollution() -> None:
    with TestClient(create_app(_make_settings())) as client:
        dict_hk = client.get("/api/v1/meta/dictionaries", headers={"Accept-Language": "zh-HK"})
        assert dict_hk.status_code == 200
        body_hk = dict_hk.json()
        assert body_hk["violation_labels"]["DANGER_ZONE_INTRUSION"] == "危險區域入侵"
        assert body_hk["severity_labels"]["CRITICAL"] == "嚴重"
        assert body_hk["status_labels"]["ACTIVE"] == "待關注"

        dict_cn = client.get("/api/v1/meta/dictionaries", headers={"Accept-Language": "zh-CN"})
        assert dict_cn.status_code == 200
        assert dict_cn.json()["violation_labels"] == VIOLATION_LABELS
        assert dict_cn.json()["severity_labels"] == SEVERITY_LABELS

        ui_hk = client.get("/api/v1/agent/ui-config", headers={"Accept-Language": "zh-HK"})
        assert ui_hk.status_code == 200
        assert ui_hk.json()["welcome_message"] == "查詢現場風險，核對安全依據，銜接報告與培訓。"

        ui_cn = client.get("/api/v1/agent/ui-config", headers={"Accept-Language": "zh-CN"})
        assert ui_cn.status_code == 200
        assert ui_cn.json()["welcome_message"] == "查询现场风险，核对安全依据，衔接报告与培训。"

        heatmap_hk = client.get("/api/v1/safety/risk-heatmap", headers={"Accept-Language": "zh-HK"})
        assert heatmap_hk.status_code == 200
        heatmap_cn = client.get("/api/v1/safety/risk-heatmap", headers={"Accept-Language": "zh-CN"})
        assert heatmap_cn.status_code == 200
        # Ensure zh-HK request did not pollute cache for zh-CN
        assert heatmap_hk.json()["summary"] != heatmap_cn.json()["summary"] or "暫無" in heatmap_hk.json()["summary"] or "近" in heatmap_cn.json()["summary"]
        assert to_simplified_text(heatmap_hk.json()["summary"]) == heatmap_cn.json()["summary"]


def test_agent_chat_supports_traditional_chinese_roundtrip() -> None:
    with TestClient(create_app(_make_settings())) as client:
        resp_hk = client.post(
            "/api/v1/agent/chat",
            headers={"Accept-Language": "zh-HK"},
            json=ChatRequest(question="查看所有攝像頭狀態", conversation_id="conv-hk-1").model_dump(),
        )
        assert resp_hk.status_code == 200
        data_hk = resp_hk.json()
        assert data_hk["tool_trace"]
        assert data_hk["tool_trace"][0]["tool_name"] == "get_all_camera_statuses"
        assert "攝像頭" in data_hk["answer"] or "查詢" in data_hk["answer"]
        assert data_hk["answer"] == localize_text(data_hk["answer"], "zh-HK")

        resp_cn = client.post(
            "/api/v1/agent/chat",
            headers={"Accept-Language": "zh-CN"},
            json=ChatRequest(question="查看所有摄像头状态", conversation_id="conv-cn-1").model_dump(),
        )
        assert resp_cn.status_code == 200
        data_cn = resp_cn.json()
        assert data_cn["answer"] == to_simplified_text(data_cn["answer"])
