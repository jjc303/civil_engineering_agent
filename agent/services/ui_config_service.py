from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4
from sqlalchemy.orm import Session

from agent.contracts.ui_config import AssistantUiConfig, AssistantUiConfigUpdate, MascotProfile
from agent.db.models import AssistantUiConfigAuditModel, AssistantUiConfigModel

if TYPE_CHECKING:
    from agent.core.config import Settings

CONFIG_ID = "agent_copilot"

DEFAULT_MASCOT_PROFILE = MascotProfile()

DEFAULT_ASSISTANT_UI_CONFIG = AssistantUiConfig(
    version=0,
    assistant_name="安全智能助手",
    welcome_message="查询现场风险，核对安全依据，衔接报告与培训。",
    input_placeholder="例如：查看本周安全报告，或查询长沙当前天气",
    quick_questions=["查看所有摄像头状态", "查看最新违规事件", "查看本周安全报告"],
    show_evidence=True,
    mascot_profile=DEFAULT_MASCOT_PROFILE,
    updated_at_utc=datetime(1970, 1, 1, tzinfo=timezone.utc),
)


def mascot_profile_from_settings(settings: "Settings | None") -> MascotProfile:
    """Resolve MascotProfile from runtime Settings with safe defaults."""
    if settings is None:
        return DEFAULT_MASCOT_PROFILE
    return MascotProfile(
        enabled=settings.mascot_enabled,
        persona_name=settings.mascot_persona_name,
        idle_greeting=settings.mascot_idle_greeting,
        alert_reaction_enabled=settings.mascot_alert_reaction_enabled,
        voice_enabled_by_default=settings.mascot_voice_enabled_by_default,
    )


class UiConfigService:
    def __init__(self, session: Session, *, mascot_profile: MascotProfile | None = None) -> None:
        self.session = session
        self._mascot_profile = mascot_profile or DEFAULT_MASCOT_PROFILE

    def get(self) -> AssistantUiConfig | None:
        row = self.session.get(AssistantUiConfigModel, CONFIG_ID)
        return self._to_contract(row) if row else None

    def get_or_default(self) -> AssistantUiConfig:
        found = self.get()
        if found is not None:
            return found
        return DEFAULT_ASSISTANT_UI_CONFIG.model_copy(update={"mascot_profile": self._mascot_profile})

    def put(self, value: AssistantUiConfigUpdate, actor: str) -> AssistantUiConfig:
        row = self.session.get(AssistantUiConfigModel, CONFIG_ID)
        if row and value.expected_version != row.version:
            raise RuntimeError("assistant UI config version conflict")
        if not row:
            if value.expected_version not in (None, 0):
                raise RuntimeError("assistant UI config version conflict")
            row = AssistantUiConfigModel(config_id=CONFIG_ID, version=1, updated_at_utc=datetime.now(timezone.utc), updated_by=actor)
            self.session.add(row)
        else:
            row.version += 1
        for field in ("assistant_name", "welcome_message", "input_placeholder", "quick_questions", "show_evidence"):
            setattr(row, field, getattr(value, field))
        row.updated_at_utc, row.updated_by = datetime.now(timezone.utc), actor
        self.session.add(AssistantUiConfigAuditModel(
            audit_id=str(uuid4()), config_id=CONFIG_ID, version=row.version, actor=actor,
            detail_safe_json={"quick_question_count": len(row.quick_questions), "show_evidence": row.show_evidence},
            created_at_utc=row.updated_at_utc,
        ))
        self.session.flush()
        return self._to_contract(row)

    def _to_contract(self, row: AssistantUiConfigModel) -> AssistantUiConfig:
        return AssistantUiConfig(
            version=row.version,
            assistant_name=row.assistant_name,
            welcome_message=row.welcome_message,
            input_placeholder=row.input_placeholder,
            quick_questions=row.quick_questions or [],
            show_evidence=row.show_evidence,
            mascot_profile=self._mascot_profile,
            updated_at_utc=row.updated_at_utc,
        )
