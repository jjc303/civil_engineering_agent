from __future__ import annotations

from dataclasses import dataclass
import json
import os
from dotenv import load_dotenv
from agent.contracts.event_v1 import ViolationSeverity
from agent.core.deployment import normalize_base_path


# Local .env values fill missing variables; deployed environment values always win.
load_dotenv(override=False)

DEFAULT_RAG_STANDARDS_SUBDIRECTORY = "standards"
DEFAULT_RAG_ACCIDENT_REPORTS_SUBDIRECTORY = "accident_reports"
DEFAULT_TOOL_MAX_CALLS = 4
MIN_TOOL_CALLS = 1
MAX_TOOL_CALLS = 5
DEFAULT_RAG_TOP_K = 4


def validate_rag_inbox_subdirectories(standards: str, accident_reports: str) -> None:
    for name in (standards, accident_reports):
        if not name or name != name.strip() or name in {".", ".."} or any(char in name for char in ("/", "\\", "\x00")):
            raise RuntimeError("RAG inbox subdirectories must be distinct, non-empty directory names")
    if standards.casefold() == accident_reports.casefold():
        raise RuntimeError("RAG inbox subdirectories must be distinct, non-empty directory names")


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    database_url: str
    internal_perception_token: str
    tool_max_calls: int = DEFAULT_TOOL_MAX_CALLS
    auto_create_schema: bool = False
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-flash"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_timeout_seconds: float = 20.0
    media_root: str = "./runs/media"
    app_base_path: str = ""
    learning_public_base_url: str = ""
    learning_report_directory: str = "./runs/learning/reports"
    learning_timezone: str = "Asia/Shanghai"
    learning_insights_ttl_seconds: int = 600
    report_source_label: str = "现场监控记录"
    pending_action_ttl_minutes: int = 15
    credential_encryption_key: str = ""
    cv_control_timeout_seconds: float = 10.0
    cv_node_offline_threshold_seconds: float = 30.0
    memory_enabled: bool = True
    memory_ttl_hours: int = 24
    memory_recent_turns: int = 6
    rag_enabled: bool = False
    rag_persist_directory: str = "./runs/chroma"
    rag_document_directory: str = "./runs/knowledge"
    rag_inbox_directory: str = "./runs/knowledge/inbox"
    rag_standards_subdirectory: str = DEFAULT_RAG_STANDARDS_SUBDIRECTORY
    rag_accident_reports_subdirectory: str = DEFAULT_RAG_ACCIDENT_REPORTS_SUBDIRECTORY
    rag_standards_on_demand: bool = False
    rag_sync_interval_seconds: int = 30
    rag_embedding_provider: str = "dashscope"
    rag_embedding_model: str = "text-embedding-v4"
    rag_embedding_api_key: str = ""
    rag_embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    rag_embedding_dimensions: int = 1024
    rag_collection_name: str = ""
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120
    rag_top_k: int = DEFAULT_RAG_TOP_K
    rag_top_k_max: int = 8
    rag_max_upload_bytes: int = 20 * 1024 * 1024
    rag_allowed_extensions: str = ".pdf,.docx,.md,.txt"
    feishu_notify_enabled: bool = True
    feishu_webhook_url: str = ""
    feishu_webhook_secret: str = ""
    feishu_web_base_url: str = "http://127.0.0.1:5173"
    feishu_alert_cooldown_seconds: int = 60
    feishu_alert_min_severity: str = "WARNING"
    feishu_timeout_seconds: float = 5.0
    feishu_max_workers: int = 2
    feishu_shutdown_wait_seconds: float = 3.0
    feishu_brand_name: str = "智慧施工安全智能体"
    feishu_summary_max_chars: int = 200
    feishu_remediation_max_chars: int = 160
    feishu_material_preview_max_chars: int = 150
    feishu_test_default_title: str = "施工安全飞书联动自检通报"
    feishu_test_default_content: str = (
        "✅ **飞书自定义机器人通道已就绪**\n"
        "- 边缘感知高危违规实时告警已开启\n"
        "- 整改任务派发与销项闭环通知已开启\n"
        "- 安全周报与全员培训发布推送已开启"
    )
    feishu_standard_hints_json: str = ""
    feishu_route_dashboard: str = "/dashboard"
    feishu_route_violations: str = "/violations"
    feishu_route_rectification_tasks: str = "/rectification-tasks"
    feishu_route_copilot: str = "/copilot"
    feishu_route_learning: str = "/learning"
    redis_url: str = ""
    redis_key_prefix: str = "cea"
    redis_socket_timeout_seconds: float = 2.0
    cache_stats_ttl_seconds: int = 15
    cache_camera_status_ttl_seconds: int = 30
    lock_default_ttl_seconds: int = 30
    lock_rag_sync_ttl_seconds: int = 120
    lock_action_confirm_ttl_seconds: int = 60
    lock_watchdog_interval_ratio: float = 0.33
    stream_violation_events_key: str = "streams:violation_events"
    stream_consumer_group: str = "agent_notification_workers"
    stream_async_enabled: bool = False
    pubsub_realtime_channel: str = "pubsub:realtime_events"
    sse_keepalive_seconds: float = 15.0
    mascot_enabled: bool = True
    mascot_persona_name: str = "安小盾"
    mascot_idle_greeting: str = "我是施工安全卫士安小盾，随时为您巡检风险与解答规范。"
    mascot_alert_reaction_enabled: bool = True
    mascot_voice_enabled_by_default: bool = False
    bind_host: str = ""
    port: int = 0
    cors_origins: tuple[str, ...] = ()

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_provider=os.getenv("AGENT_LLM_PROVIDER", "deepseek").lower(),
            llm_model=os.getenv("AGENT_LLM_MODEL", "deepseek-flash"),
            llm_base_url=os.getenv("AGENT_LLM_BASE_URL", "https://api.deepseek.com"),
            llm_api_key=os.getenv("AGENT_LLM_API_KEY", ""),
            llm_timeout_seconds=float(os.getenv("AGENT_LLM_TIMEOUT_SECONDS", "20")),
            database_url=os.getenv("AGENT_DATABASE_URL", ""),
            tool_max_calls=int(os.getenv("AGENT_TOOL_MAX_CALLS", str(DEFAULT_TOOL_MAX_CALLS))),
            internal_perception_token=os.getenv("INTERNAL_PERCEPTION_TOKEN", ""),
            auto_create_schema=os.getenv("AGENT_AUTO_CREATE_SCHEMA", "false").lower() == "true",
            media_root=os.getenv("AGENT_MEDIA_ROOT", "./runs/media"),
            app_base_path=normalize_base_path(os.getenv("APP_BASE_PATH", "")),
            learning_public_base_url=os.getenv("LEARNING_PUBLIC_BASE_URL", ""),
            learning_report_directory=os.getenv("LEARNING_REPORT_DIRECTORY", "./runs/learning/reports"),
            learning_timezone=os.getenv("LEARNING_TIMEZONE", "Asia/Shanghai"),
            learning_insights_ttl_seconds=int(os.getenv("LEARNING_INSIGHTS_TTL_SECONDS", "600")),
            report_source_label=os.getenv("REPORT_SOURCE_LABEL", "现场监控记录"),
            pending_action_ttl_minutes=int(os.getenv("AGENT_PENDING_ACTION_TTL_MINUTES", "15")),
            credential_encryption_key=os.getenv("AGENT_CREDENTIAL_ENCRYPTION_KEY", ""),
            cv_control_timeout_seconds=float(os.getenv("AGENT_CV_CONTROL_TIMEOUT_SECONDS", "10")),
            cv_node_offline_threshold_seconds=float(os.getenv("AGENT_CV_NODE_OFFLINE_SECONDS", "30")),
            memory_enabled=os.getenv("AGENT_MEMORY_ENABLED", "true").lower() == "true",
            memory_ttl_hours=int(os.getenv("AGENT_MEMORY_TTL_HOURS", "24")),
            memory_recent_turns=int(os.getenv("AGENT_MEMORY_RECENT_TURNS", "6")),
            rag_enabled=os.getenv("AGENT_RAG_ENABLED", "false").lower() == "true",
            rag_persist_directory=os.getenv("AGENT_RAG_PERSIST_DIRECTORY", "./runs/chroma"),
            rag_document_directory=os.getenv("AGENT_RAG_DOCUMENT_DIRECTORY", "./runs/knowledge"),
            rag_inbox_directory=os.getenv("AGENT_RAG_INBOX_DIRECTORY", "./runs/knowledge/inbox"),
            rag_standards_subdirectory=os.getenv("AGENT_RAG_STANDARDS_SUBDIRECTORY", DEFAULT_RAG_STANDARDS_SUBDIRECTORY),
            rag_accident_reports_subdirectory=os.getenv("AGENT_RAG_ACCIDENT_REPORTS_SUBDIRECTORY", DEFAULT_RAG_ACCIDENT_REPORTS_SUBDIRECTORY),
            rag_standards_on_demand=os.getenv("AGENT_RAG_STANDARDS_ON_DEMAND", "false").lower() == "true",
            rag_sync_interval_seconds=int(os.getenv("AGENT_RAG_SYNC_INTERVAL_SECONDS", "30")),
            rag_embedding_provider=os.getenv("AGENT_RAG_EMBEDDING_PROVIDER", "dashscope").lower(),
            rag_embedding_model=os.getenv("AGENT_RAG_EMBEDDING_MODEL", "text-embedding-v4"),
            # DASHSCOPE_API_KEY is the standard name used by Alibaba Cloud's SDK
            # and is accepted as a backwards-compatible fallback.
            rag_embedding_api_key=os.getenv("AGENT_RAG_EMBEDDING_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")),
            rag_embedding_base_url=os.getenv("AGENT_RAG_EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            rag_embedding_dimensions=int(os.getenv("AGENT_RAG_EMBEDDING_DIMENSIONS", "1024")),
            rag_collection_name=os.getenv("AGENT_RAG_COLLECTION_NAME", "").strip(),
            rag_chunk_size=int(os.getenv("AGENT_RAG_CHUNK_SIZE", "800")),
            rag_chunk_overlap=int(os.getenv("AGENT_RAG_CHUNK_OVERLAP", "120")),
            rag_top_k=int(os.getenv("AGENT_RAG_TOP_K", str(DEFAULT_RAG_TOP_K))),
            rag_top_k_max=int(os.getenv("AGENT_RAG_TOP_K_MAX", "8")),
            rag_max_upload_bytes=int(os.getenv("AGENT_RAG_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024))),
            rag_allowed_extensions=os.getenv("AGENT_RAG_ALLOWED_EXTENSIONS", ".pdf,.docx,.md,.txt"),
            feishu_notify_enabled=os.getenv("FEISHU_NOTIFY_ENABLED", "true").lower() == "true",
            feishu_webhook_url=os.getenv("FEISHU_WEBHOOK_URL", "").strip(),
            feishu_webhook_secret=os.getenv("FEISHU_WEBHOOK_SECRET", "").strip(),
            feishu_web_base_url=os.getenv("FEISHU_WEB_BASE_URL", os.getenv("LEARNING_PUBLIC_BASE_URL", "http://127.0.0.1:5173")).strip().rstrip("/"),
            feishu_alert_cooldown_seconds=int(os.getenv("FEISHU_ALERT_COOLDOWN_SECONDS", "60")),
            feishu_alert_min_severity=os.getenv("FEISHU_ALERT_MIN_SEVERITY", "WARNING").upper().strip(),
            feishu_timeout_seconds=float(os.getenv("FEISHU_TIMEOUT_SECONDS", "5.0")),
            feishu_max_workers=int(os.getenv("FEISHU_MAX_WORKERS", "2")),
            feishu_shutdown_wait_seconds=float(os.getenv("FEISHU_SHUTDOWN_WAIT_SECONDS", "3.0")),
            feishu_brand_name=os.getenv("FEISHU_BRAND_NAME", "智慧施工安全智能体").strip() or "智慧施工安全智能体",
            feishu_summary_max_chars=int(os.getenv("FEISHU_SUMMARY_MAX_CHARS", "200")),
            feishu_remediation_max_chars=int(os.getenv("FEISHU_REMEDIATION_MAX_CHARS", "160")),
            feishu_material_preview_max_chars=int(os.getenv("FEISHU_MATERIAL_PREVIEW_MAX_CHARS", "150")),
            feishu_test_default_title=os.getenv("FEISHU_TEST_DEFAULT_TITLE", "施工安全飞书联动自检通报").strip() or "施工安全飞书联动自检通报",
            feishu_test_default_content=os.getenv(
                "FEISHU_TEST_DEFAULT_CONTENT",
                "✅ **飞书自定义机器人通道已就绪**\n- 边缘感知高危违规实时告警已开启\n- 整改任务派发与销项闭环通知已开启\n- 安全周报与全员培训发布推送已开启",
            ),
            feishu_standard_hints_json=os.getenv("FEISHU_STANDARD_HINTS_JSON", "").strip(),
            feishu_route_dashboard=os.getenv("FEISHU_ROUTE_DASHBOARD", "/dashboard").strip() or "/dashboard",
            feishu_route_violations=os.getenv("FEISHU_ROUTE_VIOLATIONS", "/violations").strip() or "/violations",
            feishu_route_rectification_tasks=os.getenv("FEISHU_ROUTE_RECTIFICATION_TASKS", "/rectification-tasks").strip() or "/rectification-tasks",
            feishu_route_copilot=os.getenv("FEISHU_ROUTE_COPILOT", "/copilot").strip() or "/copilot",
            feishu_route_learning=os.getenv("FEISHU_ROUTE_LEARNING", "/learning").strip() or "/learning",
            redis_url=os.getenv("AGENT_REDIS_URL", "").strip(),
            redis_key_prefix=os.getenv("AGENT_REDIS_KEY_PREFIX", "cea").strip() or "cea",
            redis_socket_timeout_seconds=float(os.getenv("AGENT_REDIS_SOCKET_TIMEOUT_SECONDS", "2.0")),
            cache_stats_ttl_seconds=int(os.getenv("AGENT_CACHE_STATS_TTL_SECONDS", "15")),
            cache_camera_status_ttl_seconds=int(os.getenv("AGENT_CACHE_CAMERA_STATUS_TTL_SECONDS", "30")),
            lock_default_ttl_seconds=int(os.getenv("AGENT_LOCK_DEFAULT_TTL_SECONDS", "30")),
            lock_rag_sync_ttl_seconds=int(os.getenv("AGENT_LOCK_RAG_SYNC_TTL_SECONDS", "120")),
            lock_action_confirm_ttl_seconds=int(os.getenv("AGENT_LOCK_ACTION_CONFIRM_TTL_SECONDS", "60")),
            lock_watchdog_interval_ratio=float(os.getenv("AGENT_LOCK_WATCHDOG_INTERVAL_RATIO", "0.33")),
            stream_violation_events_key=os.getenv("AGENT_STREAM_VIOLATION_EVENTS_KEY", "streams:violation_events").strip() or "streams:violation_events",
            stream_consumer_group=os.getenv("AGENT_STREAM_CONSUMER_GROUP", "agent_notification_workers").strip() or "agent_notification_workers",
            stream_async_enabled=os.getenv("AGENT_STREAM_ASYNC_ENABLED", "false").lower() == "true",
            pubsub_realtime_channel=os.getenv("AGENT_PUBSUB_REALTIME_CHANNEL", "pubsub:realtime_events").strip() or "pubsub:realtime_events",
            sse_keepalive_seconds=float(os.getenv("AGENT_SSE_KEEPALIVE_SECONDS", "15")),
            mascot_enabled=os.getenv("AGENT_MASCOT_ENABLED", "true").lower() == "true",
            mascot_persona_name=os.getenv("AGENT_MASCOT_PERSONA_NAME", "安小盾").strip() or "安小盾",
            mascot_idle_greeting=(
                os.getenv(
                    "AGENT_MASCOT_IDLE_GREETING",
                    "我是施工安全卫士安小盾，随时为您巡检风险与解答规范。",
                ).strip()
                or "我是施工安全卫士安小盾，随时为您巡检风险与解答规范。"
            ),
            mascot_alert_reaction_enabled=os.getenv("AGENT_MASCOT_ALERT_REACTION_ENABLED", "true").lower() == "true",
            mascot_voice_enabled_by_default=os.getenv("AGENT_MASCOT_VOICE_DEFAULT", "false").lower() == "true",
            bind_host=_required("AGENT_BIND_HOST"),
            port=int(_required("AGENT_PORT")),
            cors_origins=tuple(origin.strip() for origin in _required("AGENT_CORS_ORIGINS").split(",") if origin.strip()),
        )

    def validate_for_runtime(self) -> None:
        from zoneinfo import ZoneInfo
        try:
            ZoneInfo(self.learning_timezone)
        except (KeyError, ValueError) as exc:
            raise RuntimeError("LEARNING_TIMEZONE must be a valid IANA time zone") from exc
        if not self.database_url:
            raise RuntimeError("AGENT_DATABASE_URL must be configured")
        if not self.internal_perception_token:
            raise RuntimeError("INTERNAL_PERCEPTION_TOKEN must be configured")
        if not MIN_TOOL_CALLS <= self.tool_max_calls <= MAX_TOOL_CALLS:
            raise RuntimeError(f"AGENT_TOOL_MAX_CALLS must be between {MIN_TOOL_CALLS} and {MAX_TOOL_CALLS}")
        from agent.llm.factory import supported_providers
        if self.llm_provider not in supported_providers():
            raise RuntimeError("AGENT_LLM_PROVIDER must be fake or deepseek")
        if self.llm_provider == "deepseek" and not self.llm_api_key:
            raise RuntimeError("AGENT_LLM_API_KEY must be configured for DeepSeek")
        if self.llm_timeout_seconds <= 0:
            raise RuntimeError("AGENT_LLM_TIMEOUT_SECONDS must be positive")
        if self.cv_control_timeout_seconds <= 0:
            raise RuntimeError("AGENT_CV_CONTROL_TIMEOUT_SECONDS must be positive")
        if self.cv_node_offline_threshold_seconds <= 0:
            raise RuntimeError("AGENT_CV_NODE_OFFLINE_SECONDS must be positive")
        if self.learning_insights_ttl_seconds < 0:
            raise RuntimeError("LEARNING_INSIGHTS_TTL_SECONDS must be non-negative")
        if self.pending_action_ttl_minutes <= 0:
            raise RuntimeError("AGENT_PENDING_ACTION_TTL_MINUTES must be positive")
        if self.memory_ttl_hours <= 0 or self.memory_recent_turns < 0:
            raise RuntimeError("AGENT_MEMORY_TTL_HOURS must be positive and AGENT_MEMORY_RECENT_TURNS non-negative")
        if self.rag_chunk_size <= 0 or not 0 <= self.rag_chunk_overlap < self.rag_chunk_size:
            raise RuntimeError("AGENT_RAG_CHUNK_OVERLAP must be non-negative and smaller than AGENT_RAG_CHUNK_SIZE")
        if self.rag_sync_interval_seconds <= 0:
            raise RuntimeError("AGENT_RAG_SYNC_INTERVAL_SECONDS must be positive")
        validate_rag_inbox_subdirectories(self.rag_standards_subdirectory, self.rag_accident_reports_subdirectory)
        if not 1 <= self.rag_top_k <= self.rag_top_k_max:
            raise RuntimeError("AGENT_RAG_TOP_K must be between 1 and AGENT_RAG_TOP_K_MAX")
        if self.redis_socket_timeout_seconds <= 0:
            raise RuntimeError("AGENT_REDIS_SOCKET_TIMEOUT_SECONDS must be positive")
        if self.cache_stats_ttl_seconds < 0 or self.cache_camera_status_ttl_seconds < 0:
            raise RuntimeError("Cache TTL settings must be non-negative")
        if self.lock_default_ttl_seconds <= 0 or self.lock_rag_sync_ttl_seconds <= 0 or self.lock_action_confirm_ttl_seconds <= 0:
            raise RuntimeError("Lock TTL settings must be positive")
        if not (0.05 <= self.lock_watchdog_interval_ratio <= 0.8):
            raise RuntimeError("AGENT_LOCK_WATCHDOG_INTERVAL_RATIO must be between 0.05 and 0.8")
        if self.feishu_alert_min_severity not in {s.value for s in ViolationSeverity}:
            raise RuntimeError("FEISHU_ALERT_MIN_SEVERITY must be INFO, WARNING, or CRITICAL")
        if self.feishu_alert_cooldown_seconds < 0:
            raise RuntimeError("FEISHU_ALERT_COOLDOWN_SECONDS must be non-negative")
        if self.feishu_timeout_seconds <= 0:
            raise RuntimeError("FEISHU_TIMEOUT_SECONDS must be positive")
        if self.feishu_max_workers < 1:
            raise RuntimeError("FEISHU_MAX_WORKERS must be at least 1")
        if self.feishu_shutdown_wait_seconds < 0:
            raise RuntimeError("FEISHU_SHUTDOWN_WAIT_SECONDS must be non-negative")
        if min(
            self.feishu_summary_max_chars,
            self.feishu_remediation_max_chars,
            self.feishu_material_preview_max_chars,
        ) <= 0:
            raise RuntimeError("FEISHU_*_MAX_CHARS settings must be positive")
        self.parsed_feishu_standard_hints()
        from agent.rag.chroma_adapter import validate_embedding_settings
        validate_embedding_settings(
            self.rag_embedding_provider,
            self.rag_embedding_model,
            self.rag_embedding_api_key,
            self.rag_embedding_base_url,
            self.rag_embedding_dimensions,
            self.rag_enabled,
        )
        if self.sse_keepalive_seconds <= 0:
            raise RuntimeError("AGENT_SSE_KEEPALIVE_SECONDS must be positive")
        if not self.auto_create_schema and (not self.bind_host or not 1 <= self.port <= 65535 or not self.cors_origins):
            raise RuntimeError("AGENT_BIND_HOST, AGENT_PORT and AGENT_CORS_ORIGINS must be configured")

    def parsed_feishu_standard_hints(self) -> dict[str, str]:
        """Parse optional JSON mapping of violation_type -> standard hint overrides."""
        raw = self.feishu_standard_hints_json.strip()
        if not raw:
            return {}
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("FEISHU_STANDARD_HINTS_JSON must be valid JSON") from exc
        if not isinstance(loaded, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in loaded.items()
        ):
            raise RuntimeError("FEISHU_STANDARD_HINTS_JSON must be a JSON object mapping strings to strings")
        return loaded

    def feishu_routes(self) -> dict[str, str]:
        """Return configured frontend route mapping for notification action links."""
        return {
            "dashboard": self.feishu_route_dashboard,
            "violations": self.feishu_route_violations,
            "rectification_tasks": self.feishu_route_rectification_tasks,
            "copilot": self.feishu_route_copilot,
            "learning": self.feishu_route_learning,
        }


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be configured")
    return value
