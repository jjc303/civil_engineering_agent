from __future__ import annotations

from dataclasses import dataclass
import os
from dotenv import load_dotenv


# Local .env values fill missing variables; deployed environment values always win.
load_dotenv(override=False)

DEFAULT_RAG_STANDARDS_SUBDIRECTORY = "standards"
DEFAULT_RAG_ACCIDENT_REPORTS_SUBDIRECTORY = "accident_reports"


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
    tool_max_calls: int = 2
    auto_create_schema: bool = False
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-flash"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_timeout_seconds: float = 20.0
    media_root: str = "./runs/media"
    admin_token: str = ""
    credential_encryption_key: str = ""
    cv_control_timeout_seconds: float = 10.0
    memory_enabled: bool = True
    memory_ttl_hours: int = 24
    memory_recent_turns: int = 6
    rag_enabled: bool = False
    rag_persist_directory: str = "./runs/chroma"
    rag_document_directory: str = "./runs/knowledge"
    rag_inbox_directory: str = "./runs/knowledge/inbox"
    rag_standards_subdirectory: str = DEFAULT_RAG_STANDARDS_SUBDIRECTORY
    rag_accident_reports_subdirectory: str = DEFAULT_RAG_ACCIDENT_REPORTS_SUBDIRECTORY
    rag_sync_interval_seconds: int = 30
    rag_embedding_provider: str = "dashscope"
    rag_embedding_model: str = "text-embedding-v4"
    rag_embedding_api_key: str = ""
    rag_embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    rag_embedding_dimensions: int = 1024
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120
    rag_top_k: int = 4
    rag_top_k_max: int = 8
    rag_max_upload_bytes: int = 20 * 1024 * 1024
    rag_allowed_extensions: str = ".pdf,.docx,.md,.txt"
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
            tool_max_calls=int(os.getenv("AGENT_TOOL_MAX_CALLS", "2")),
            internal_perception_token=os.getenv("INTERNAL_PERCEPTION_TOKEN", ""),
            auto_create_schema=os.getenv("AGENT_AUTO_CREATE_SCHEMA", "false").lower() == "true",
            media_root=os.getenv("AGENT_MEDIA_ROOT", "./runs/media"),
            admin_token=os.getenv("AGENT_ADMIN_TOKEN", ""),
            credential_encryption_key=os.getenv("AGENT_CREDENTIAL_ENCRYPTION_KEY", ""),
            cv_control_timeout_seconds=float(os.getenv("AGENT_CV_CONTROL_TIMEOUT_SECONDS", "10")),
            memory_enabled=os.getenv("AGENT_MEMORY_ENABLED", "true").lower() == "true",
            memory_ttl_hours=int(os.getenv("AGENT_MEMORY_TTL_HOURS", "24")),
            memory_recent_turns=int(os.getenv("AGENT_MEMORY_RECENT_TURNS", "6")),
            rag_enabled=os.getenv("AGENT_RAG_ENABLED", "false").lower() == "true",
            rag_persist_directory=os.getenv("AGENT_RAG_PERSIST_DIRECTORY", "./runs/chroma"),
            rag_document_directory=os.getenv("AGENT_RAG_DOCUMENT_DIRECTORY", "./runs/knowledge"),
            rag_inbox_directory=os.getenv("AGENT_RAG_INBOX_DIRECTORY", "./runs/knowledge/inbox"),
            rag_standards_subdirectory=os.getenv("AGENT_RAG_STANDARDS_SUBDIRECTORY", DEFAULT_RAG_STANDARDS_SUBDIRECTORY),
            rag_accident_reports_subdirectory=os.getenv("AGENT_RAG_ACCIDENT_REPORTS_SUBDIRECTORY", DEFAULT_RAG_ACCIDENT_REPORTS_SUBDIRECTORY),
            rag_sync_interval_seconds=int(os.getenv("AGENT_RAG_SYNC_INTERVAL_SECONDS", "30")),
            rag_embedding_provider=os.getenv("AGENT_RAG_EMBEDDING_PROVIDER", "dashscope").lower(),
            rag_embedding_model=os.getenv("AGENT_RAG_EMBEDDING_MODEL", "text-embedding-v4"),
            # DASHSCOPE_API_KEY is the standard name used by Alibaba Cloud's SDK
            # and is accepted as a backwards-compatible fallback.
            rag_embedding_api_key=os.getenv("AGENT_RAG_EMBEDDING_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")),
            rag_embedding_base_url=os.getenv("AGENT_RAG_EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            rag_embedding_dimensions=int(os.getenv("AGENT_RAG_EMBEDDING_DIMENSIONS", "1024")),
            rag_chunk_size=int(os.getenv("AGENT_RAG_CHUNK_SIZE", "800")),
            rag_chunk_overlap=int(os.getenv("AGENT_RAG_CHUNK_OVERLAP", "120")),
            rag_top_k=int(os.getenv("AGENT_RAG_TOP_K", "4")),
            rag_top_k_max=int(os.getenv("AGENT_RAG_TOP_K_MAX", "8")),
            rag_max_upload_bytes=int(os.getenv("AGENT_RAG_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024))),
            rag_allowed_extensions=os.getenv("AGENT_RAG_ALLOWED_EXTENSIONS", ".pdf,.docx,.md,.txt"),
            bind_host=_required("AGENT_BIND_HOST"),
            port=int(_required("AGENT_PORT")),
            cors_origins=tuple(origin.strip() for origin in _required("AGENT_CORS_ORIGINS").split(",") if origin.strip()),
        )

    def validate_for_runtime(self) -> None:
        if not self.database_url:
            raise RuntimeError("AGENT_DATABASE_URL must be configured")
        if not self.internal_perception_token:
            raise RuntimeError("INTERNAL_PERCEPTION_TOKEN must be configured")
        if not 1 <= self.tool_max_calls <= 2:
            raise RuntimeError("AGENT_TOOL_MAX_CALLS must be between 1 and 2")
        if self.llm_provider not in {"fake", "deepseek"}:
            raise RuntimeError("AGENT_LLM_PROVIDER must be fake or deepseek")
        if self.llm_provider == "deepseek" and not self.llm_api_key:
            raise RuntimeError("AGENT_LLM_API_KEY must be configured for DeepSeek")
        if self.llm_timeout_seconds <= 0:
            raise RuntimeError("AGENT_LLM_TIMEOUT_SECONDS must be positive")
        if self.cv_control_timeout_seconds <= 0:
            raise RuntimeError("AGENT_CV_CONTROL_TIMEOUT_SECONDS must be positive")
        if self.memory_ttl_hours <= 0 or self.memory_recent_turns < 0:
            raise RuntimeError("AGENT_MEMORY_TTL_HOURS must be positive and AGENT_MEMORY_RECENT_TURNS non-negative")
        if self.rag_chunk_size <= 0 or not 0 <= self.rag_chunk_overlap < self.rag_chunk_size:
            raise RuntimeError("AGENT_RAG_CHUNK_OVERLAP must be non-negative and smaller than AGENT_RAG_CHUNK_SIZE")
        if self.rag_sync_interval_seconds <= 0:
            raise RuntimeError("AGENT_RAG_SYNC_INTERVAL_SECONDS must be positive")
        validate_rag_inbox_subdirectories(self.rag_standards_subdirectory, self.rag_accident_reports_subdirectory)
        if not 1 <= self.rag_top_k <= self.rag_top_k_max:
            raise RuntimeError("AGENT_RAG_TOP_K must be between 1 and AGENT_RAG_TOP_K_MAX")
        if self.rag_embedding_provider not in {"dashscope", "sentence_transformers"}:
            raise RuntimeError("AGENT_RAG_EMBEDDING_PROVIDER must be dashscope or sentence_transformers")
        if self.rag_embedding_provider == "dashscope":
            if self.rag_embedding_model != "text-embedding-v4":
                raise RuntimeError("AGENT_RAG_EMBEDDING_MODEL must be text-embedding-v4 for the dashscope provider")
            if self.rag_embedding_dimensions not in {64, 128, 256, 512, 768, 1024, 1536, 2048}:
                raise RuntimeError("AGENT_RAG_EMBEDDING_DIMENSIONS is not supported by text-embedding-v4")
            if self.rag_enabled and not self.rag_embedding_api_key:
                raise RuntimeError("AGENT_RAG_EMBEDDING_API_KEY or DASHSCOPE_API_KEY must be configured when RAG is enabled")
            if self.rag_enabled and not self.rag_embedding_base_url:
                raise RuntimeError("AGENT_RAG_EMBEDDING_BASE_URL must be configured when RAG is enabled")
        if not self.auto_create_schema and (not self.bind_host or not 1 <= self.port <= 65535 or not self.cors_origins):
            raise RuntimeError("AGENT_BIND_HOST, AGENT_PORT and AGENT_CORS_ORIGINS must be configured")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be configured")
    return value
