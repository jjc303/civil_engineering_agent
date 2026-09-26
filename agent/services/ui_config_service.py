from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.orm import Session

from agent.contracts.ui_config import AssistantUiConfig, AssistantUiConfigUpdate
from agent.db.models import AssistantUiConfigAuditModel, AssistantUiConfigModel

CONFIG_ID = "agent_copilot"


class UiConfigService:
    def __init__(self, session: Session) -> None: self.session = session
    def get(self) -> AssistantUiConfig | None:
        row = self.session.get(AssistantUiConfigModel, CONFIG_ID)
        return self._to_contract(row) if row else None
    def put(self, value: AssistantUiConfigUpdate, actor: str) -> AssistantUiConfig:
        row = self.session.get(AssistantUiConfigModel, CONFIG_ID)
        if row and value.expected_version != row.version: raise RuntimeError("assistant UI config version conflict")
        if not row:
            if value.expected_version not in (None, 0): raise RuntimeError("assistant UI config version conflict")
            row = AssistantUiConfigModel(config_id=CONFIG_ID, version=1, updated_at_utc=datetime.now(timezone.utc), updated_by=actor)
            self.session.add(row)
        else: row.version += 1
        for field in ("assistant_name", "welcome_message", "input_placeholder", "quick_questions", "show_evidence"):
            setattr(row, field, getattr(value, field))
        row.updated_at_utc, row.updated_by = datetime.now(timezone.utc), actor
        self.session.add(AssistantUiConfigAuditModel(audit_id=str(uuid4()), config_id=CONFIG_ID, version=row.version, actor=actor, detail_safe_json={"quick_question_count": len(row.quick_questions), "show_evidence": row.show_evidence}, created_at_utc=row.updated_at_utc))
        self.session.flush()
        return self._to_contract(row)
    @staticmethod
    def _to_contract(row: AssistantUiConfigModel) -> AssistantUiConfig:
        return AssistantUiConfig(version=row.version, assistant_name=row.assistant_name, welcome_message=row.welcome_message, input_placeholder=row.input_placeholder, quick_questions=row.quick_questions or [], show_evidence=row.show_evidence, updated_at_utc=row.updated_at_utc)
