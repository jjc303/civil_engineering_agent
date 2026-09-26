from __future__ import annotations

from dataclasses import dataclass
import os
from dotenv import load_dotenv


# Local .env values fill missing variables; deployed environment values always win.
load_dotenv(override=False)

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
    rag_embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
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
            rag_embedding_model=os.getenv("AGENT_RAG_EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"),
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
        if not 1 <= self.rag_top_k <= self.rag_top_k_max:
            raise RuntimeError("AGENT_RAG_TOP_K must be between 1 and AGENT_RAG_TOP_K_MAX")
        if not self.auto_create_schema and (not self.bind_host or not 1 <= self.port <= 65535 or not self.cors_origins):
            raise RuntimeError("AGENT_BIND_HOST, AGENT_PORT and AGENT_CORS_ORIGINS must be configured")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be configured")
    return value
