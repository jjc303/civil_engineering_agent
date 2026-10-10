from datetime import datetime

from agent.contracts.rectification import RectificationTaskRecord, RectificationTaskAudit


def test_sqlite_task_deadline_keeps_its_utc_in_the_response():
    stamp = datetime(2026, 10, 11, 10)
    record = RectificationTaskRecord(task_id="demo", event_uuid="demo-event", title="演示", owner="演示安全员",
        due_at_utc=stamp, status="PENDING", created_at_utc=stamp, updated_at_utc=stamp,
        camera_id="cam_demo_01", violation_type="NO_HELMET", severity="WARNING",
        violation_status="RESOLVED", occurred_at_utc=stamp)
    result = record.model_dump(mode="json")
    assert result["due_at_utc"] == "2026-10-11T10:00:00Z"
    assert result["completed_at_utc"] is None
    audit = RectificationTaskAudit(audit_id="demo", task_id="demo", action="CREATED", actor="ui", created_at_utc=stamp)
    assert audit.model_dump(mode="json")["created_at_utc"] == "2026-10-11T10:00:00Z"
