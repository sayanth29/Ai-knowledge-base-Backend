# app/core/config.py

from typing import Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Environment ──────────────────────────────────────────────
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str

    # ── External services ────────────────────────────────────────
    GEMINI_API_KEY: str
    QDRANT_URL: str = "http://localhost:6333"

    # ── Auth / JWT ───────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── CORS ─────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # ── Validation ───────────────────────────────────────────────

    # ── AWS  ───────────────────────────────────────────────
    AWS_REGION: str = "ap-south-1"
    AWS_S3_BUCKET: str
    AWS_PROFILE: str | None = None
    


    @field_validator("DEBUG", mode="before")
    @classmethod
    def _parse_debug(cls, v: Any) -> bool:
        if isinstance(v, str):
            val = v.strip().lower()
            if val in {"release", "prod", "production", "false", "0", "no", "off"}:
                return False
            if val in {"debug", "dev", "development", "true", "1", "yes", "on"}:
                return True
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _secret_must_not_be_placeholder(cls, v: str) -> str:
        weak = {"change_this_to_a_long_random_secret", "secret", "changeme", ""}
        if v.lower() in weak or len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY is too weak or still a placeholder. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
