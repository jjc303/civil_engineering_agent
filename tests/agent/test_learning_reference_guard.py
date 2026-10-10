import pytest
from datetime import datetime, timezone
from types import SimpleNamespace
from sqlalchemy import select
from agent.contracts.learning import ReportCreate, ReportResponse
from agent.db.base import Database
from agent.db.models import SafetyReportModel
from agent.services.learning_service import LearningService

from agent.services.learning_service import _guard_standard_references


def test_book_title_marks_accept_a_supplied_document_title():
    title = "建设工程安全生产管理条例(国务院令第393号)"
    _guard_standard_references([f"依据《{title}》采取措施。"], [title])


def test_an_unsupplied_standard_is_still_rejected():
    with pytest.raises(ValueError, match="unsupported"):
        _guard_standard_references(["依据《另一份未提供的规范》采取措施。"], ["施工安全规范"])


def test_an_unsupplied_clause_is_still_rejected():
    with pytest.raises(ValueError, match="unsupported"):
        _guard_standard_references(["根据第九十九条执行。"], ["第三条：安全规定。"])


def test_sqlite_naive_report_times_are_serialized_as_utc():
    response = ReportResponse(report_id="demo", period_start_utc=datetime(2026, 10, 10, 11, 3),
        period_end_utc=datetime(2026, 10, 10, 11, 5), created_at_utc=datetime(2026, 10, 10, 11, 29),
        status="DRAFT", statistics={}, citations=[],
        content={"summary": "演示", "risk_analysis": "核查", "remediation": "整改"})
    serialized = response.model_dump(mode="json")
    assert serialized["period_start_utc"] == "2026-10-10T11:03:00Z"
    assert serialized["created_at_utc"] == "2026-10-10T11:29:00Z"


@pytest.mark.parametrize("second_valid", [True, False])
def test_report_retries_once_and_never_saves_unverified_references(tmp_path, second_valid):
    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    bad = {"summary": "依据《未提供的安全规范》", "risk_analysis": "检查风险。", "remediation": "核查现场。"}
    good = {**bad, "summary": "当前没有可引用的规范资料。"}
    class Model:
        calls = 0
        def generate_structured(self, instruction, context):
            self.calls += 1
            return bad if self.calls == 1 or not second_valid else good
    model = Model()
    service = LearningService(database, SimpleNamespace(rag_manager=None), model, str(tmp_path), "")
    period = ReportCreate(period_start_utc=datetime(2026, 10, 9, tzinfo=timezone.utc),
        period_end_utc=datetime(2026, 10, 10, tzinfo=timezone.utc))
    if second_valid:
        assert service.create_report(period).status == "DRAFT"
    else:
        with pytest.raises(ValueError, match="unsupported"):
            service.create_report(period)
    assert model.calls == 2
    with database.session() as session:
        assert len(list(session.scalars(select(SafetyReportModel)))) == int(second_valid)
