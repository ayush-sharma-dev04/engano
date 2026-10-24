"""Central configuration for Engano AI/ML Review Engine.

Uses Pydantic Settings to load and validate environment variables.
Secrets are masked and never logged or displayed.
"""

from enum import Enum
from functools import lru_cache
from typing import Optional
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderType(str, Enum):
    RULES_ONLY = "rules_only"
    OLLAMA = "ollama"
    GEMINI = "gemini"
    AUTO = "auto"


class EngineConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Provider Selection
    ai_provider: ProviderType = Field(
        default=ProviderType.RULES_ONLY,
        alias="AI_PROVIDER",
        description="Active AI provider: rules_only, ollama, gemini, or auto"
    )

    # Google Gemini Configuration
    gemini_api_key: Optional[SecretStr] = Field(
        default=None,
        alias="GEMINI_API_KEY",
        description="Google Gemini API Key"
    )
    gemini_model: str = Field(
        default="gemini-flash-lite-latest",
        alias="GEMINI_MODEL",
        description="Google Gemini model identifier"
    )

    # Local Ollama Configuration
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        alias="OLLAMA_BASE_URL",
        description="Base URL for local Ollama service"
    )
    ollama_model: str = Field(
        default="qwen2.5vl:3b",
        alias="OLLAMA_MODEL",
        description="Model identifier running in local Ollama instance"
    )

    # Brand Memory Configuration
    memory_storage_dir: str = Field(
        default="data/brand_memory",
        alias="ENGANO_MEMORY_DIR",
        description="Filesystem directory for persistent brand memory"
    )
    memory_source: str = Field(
        default="file",
        alias="ENGANO_MEMORY_SOURCE",
        description="Brand memory persistence source: 'file' (default safe local behavior), 'auto' (Supabase when configured), or 'supabase'"
    )

    @field_validator("memory_source", mode="before")
    @classmethod
    def validate_memory_source(cls, v: object) -> str:
        if isinstance(v, str):
            clean_v = v.strip().lower()
            if clean_v not in {"auto", "file", "supabase"}:
                raise ValueError(
                    "Invalid ENGANO_MEMORY_SOURCE. Must be one of: auto, file, supabase"
                )
            return clean_v
        return v  # type: ignore

    # Supabase Configuration
    supabase_url: Optional[str] = Field(
        default=None,
        alias="SUPABASE_URL",
        description="Supabase project URL"
    )
    supabase_publishable_key: Optional[SecretStr] = Field(
        default=None,
        alias="SUPABASE_PUBLISHABLE_KEY",
        description="Supabase public/anon API key"
    )
    supabase_secret_key: Optional[SecretStr] = Field(
        default=None,
        alias="SUPABASE_SECRET_KEY",
        description="Backend-only Supabase secret key for privileged brand-memory access"
    )
    brand_memory_api_key: Optional[SecretStr] = Field(
        default=None,
        alias="ENGANO_MEMORY_API_KEY",
        description="Backend-only key required by brand-memory management API endpoints"
    )

    # Retrieval-augmented context (pgvector)
    rag_enabled: bool = Field(
        default=False,
        alias="ENGANO_RAG_ENABLED",
        description="Retrieve relevant policy/memory chunks and give them to the LLM as cited context"
    )
    rag_top_k: int = Field(default=6, alias="ENGANO_RAG_TOP_K", ge=1, le=20)
    embedding_model: str = Field(
        default="gemini-embedding-001",
        alias="ENGANO_EMBEDDING_MODEL",
        description="Gemini embedding model; output is truncated to 768 dims to match pgvector"
    )

    # Execution and Review Parameters
    request_timeout_seconds: float = Field(
        default=120.0,
        alias="REQUEST_TIMEOUT_SECONDS",
        description="Global timeout in seconds for external requests"
    )
    strict_mode: bool = Field(
        default=False,
        alias="STRICT_MODE",
        description="When True, YELLOW or RED findings enforce strict reviewer approval"
    )
    safe_fallback: bool = Field(
        default=False,
        alias="SAFE_FALLBACK",
        description="Enable safe fallback to deterministic rules if provider fails"
    )

    @field_validator("ai_provider", mode="before")
    @classmethod
    def parse_provider(cls, v: object) -> ProviderType:
        if isinstance(v, str):
            clean_v = v.strip().lower()
            try:
                return ProviderType(clean_v)
            except ValueError:
                valid = [p.value for p in ProviderType]
                raise ValueError(f"Invalid AI_PROVIDER '{v}'. Must be one of: {valid}")
        return v  # type: ignore

    def validate_for_provider(self) -> None:
        """Validate settings required by the actively selected provider."""
        if self.ai_provider == ProviderType.GEMINI:
            if not self.gemini_api_key or not self.gemini_api_key.get_secret_value().strip():
                raise ValueError(
                    "GEMINI_API_KEY must be configured when AI_PROVIDER='gemini'."
                )
        elif self.ai_provider == ProviderType.OLLAMA:
            if not self.ollama_base_url.strip():
                raise ValueError(
                    "OLLAMA_BASE_URL must be configured when AI_PROVIDER='ollama'."
                )


@lru_cache()
def get_engine_config() -> EngineConfig:
    """Return cached EngineConfig instance loaded from environment."""
    return EngineConfig()
