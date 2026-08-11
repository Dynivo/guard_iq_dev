"""Application settings loaded from environment variables via pydantic-settings."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — every value is overridable via env vars or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_content_platform"
    )
    # empty = auto (SSL for non-localhost); true/require | require-insecure | false/disable
    DATABASE_SSL: str = ""
    # Optional path to Amazon RDS global-bundle.pem (recommended in production)
    DATABASE_SSL_CA: str = ""

    # ── Redis ────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── News connectors ──────────────────────────────────────
    NEWSDATA_API_KEY: str = ""
    GNEWS_API_KEY: str = ""
    GUARDIAN_API_KEY: str = ""
    CURRENTS_API_KEY: str = ""

    # ── Object storage (StorageProvider) ─────────────────────
    # local = filesystem under STORAGE_LOCAL_ROOT
    STORAGE_PROVIDER: str = "local"
    STORAGE_LOCAL_ROOT: str = "data/media"

    # Delivery Strategy — backend_stream is the M2 default; CDN/short-lived later
    DELIVERY_STRATEGY: str = "backend_stream"

    # ── JWT ──────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE-ME"
    JWT_REFRESH_SECRET_KEY: str = "CHANGE-ME-REFRESH"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days (session kept via refresh)

    # ── CORS ─────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(v) for v in parsed]
            except (json.JSONDecodeError, TypeError):
                return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value  # type: ignore[return-value]

    # ── Image Generation ─────────────────────────────────────
    IMAGE_PROVIDER: str = "mock"
    COMFYUI_BASE_URL: str = "http://localhost:8188"
    # Dev-only cloud pixels via OpenAI Images API (IMAGE_PROVIDER=openai)
    OPENAI_IMAGE_MODEL: str = "gpt-image-1"

    # ── Job Backend ───────────────────────────────────────────
    # "inline" runs work in-process; "dramatiq" requires Redis workers.
    JOB_BACKEND: str = "inline"

    # ── LLM Provider Keys ────────────────────────────────────
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    PERPLEXITY_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_API_KEY: str = ""
    VLLM_BASE_URL: str = "http://localhost:8000/v1"
    VLLM_API_KEY: str = ""
    # xAI Grok (OpenAI-compatible chat)
    GROK_API_KEY: str = ""
    GROK_BASE_URL: str = "https://api.x.ai/v1"
    # Azure OpenAI (chat)
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_DEPLOYMENT_NAME: str = "gpt-4"
    # Azure Speech (STT + optional TTS — not Azure OpenAI)
    AZURE_SPEECH_KEY: str = ""
    AZURE_SPEECH_REGION: str = ""
    AZURE_SPEECH_ENDPOINT: str = ""
    AZURE_SPEECH_LOCALE: str = "en-IN"
    AZURE_SPEECH_RECO_LANGUAGE: str = ""  # preferred over AZURE_SPEECH_LOCALE (e.g. en-IN, hi-IN)
    STT_PROVIDER: str = ""  # azure | mock (preferred)
    TTS_PROVIDER: str = ""  # azure | mock (preferred)
    TRANSCRIPTION_PROVIDER: str = "mock"  # legacy alias for STT_PROVIDER
    # Azure Translator — translate non-English transcripts only
    TRANSLATE_PROVIDER: str = "mock"  # azure | mock
    AZURE_TRANSLATOR_KEY: str = ""
    AZURE_TRANSLATOR_REGION: str = ""
    AZURE_TRANSLATOR_ENDPOINT: str = "https://api.cognitive.microsofttranslator.com"
    DEFAULT_LLM_PROVIDER: str = "mock"
    # Rotate writing/analysis across every LLM with an API key (openai, gemini, grok, …)
    # Prefer CONSENSUS_ENABLED for writing — scores all models and keeps the best draft.
    PROVIDER_MIX_ENABLED: bool = False
    AI_CACHE_BACKEND: str = "memory"  # memory | redis
    INFERENCE_BACKEND: str = "remote"  # remote | local | gpu_cluster

    # ── Consensus Engine (M17) ───────────────────────────────
    # Multi-LLM draft scoring: generate with several providers, pick best content.
    CONSENSUS_ENABLED: bool = False
    CONSENSUS_POLICY: str = "balanced"  # development|cheap|balanced|premium|enterprise

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    def validate_production_secrets(self) -> None:
        """Fail fast when production would run with placeholder JWT secrets."""
        if self.APP_ENV.lower() != "production":
            return
        insecure = {"CHANGE-ME", "CHANGE-ME-REFRESH", ""}
        if self.JWT_SECRET_KEY in insecure or self.JWT_REFRESH_SECRET_KEY in insecure:
            raise RuntimeError(
                "JWT_SECRET_KEY / JWT_REFRESH_SECRET_KEY must be set to strong "
                "values when APP_ENV=production"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    settings = Settings()
    settings.validate_production_secrets()
    return settings
