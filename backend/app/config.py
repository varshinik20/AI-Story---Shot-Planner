from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "CINEMIND"
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL async SQLAlchemy connection URL (postgresql+asyncpg://...)",
    )
    TEST_DATABASE_URL: str | None = Field(
        default=None,
        description="Separate PostgreSQL async URL for pytest integration tests.",
    )

    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key for GPT-4o story and shot-plan generation.",
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o",
        description="OpenAI model to use (gpt-4o, gpt-4-turbo, etc.).",
    )
    GEMINI_API_KEY: str | None = Field(
        default=None,
        description="Google Gemini API key for scene reference image generation.",
    )
    LLM_PROVIDER: str = Field(
        default="openai",
        description="Active LLM provider adapter name.",
    )
    LLM_TIMEOUT_SECONDS: float = Field(
        default=120.0,
        description="HTTP/SDK timeout in seconds for each LLM request.",
    )
    LLM_MAX_RETRIES: int = Field(
        default=2,
        description="Maximum retry attempts on transient LLM errors.",
    )
    LLM_MAX_TOKENS: int = Field(
        default=8192,
        description="Default maximum completion tokens per LLM call.",
    )

    SCORING_WEIGHT_EMOTION: float = 0.35
    SCORING_WEIGHT_NARRATIVE: float = 0.25
    SCORING_WEIGHT_DIRECTOR: float = 0.20
    SCORING_WEIGHT_CONTINUITY: float = 0.20

    UPLOAD_MAX_BYTES: int = 10 * 1024 * 1024

    MONGODB_URL: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URL used exclusively for authentication.",
    )
    MONGODB_DATABASE: str = Field(
        default="story_planner_auth",
        description="MongoDB database name storing authorized credentials.",
    )
    MONGODB_COLLECTION: str = Field(
        default="authorized_credentials",
        description="MongoDB collection storing the single authorized account.",
    )
    MONGODB_CONNECT_TIMEOUT_MS: int = Field(
        default=5000,
        ge=500,
        description="MongoDB connection timeout in milliseconds.",
    )

    AUTH_USERNAME: str = Field(
        default="",
        description="Initial single authorized login username (used only when bootstrapping).",
    )
    AUTH_PASSWORD: str = Field(
        default="",
        description="Initial single authorized login password (hashed with Argon2id before saving).",
    )
    JWT_SECRET_KEY: str = Field(
        default="",
        description="HMAC secret key used to sign JWT session cookies.",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm.",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60,
        ge=1,
        le=1440,
        description="JWT and HttpOnly cookie lifetime in minutes.",
    )
    AUTH_COOKIE_NAME: str = Field(
        default="storyforge_session",
        description="Cookie name storing the signed JWT session token.",
    )
    CSRF_COOKIE_NAME: str = Field(
        default="storyforge_csrf",
        description="Double-submit CSRF cookie paired with X-CSRF-Token header.",
    )
    AUTH_RATE_LIMIT_ATTEMPTS: int = Field(
        default=5,
        ge=1,
        description="Maximum login attempts per client IP inside the rate-limit window.",
    )
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = Field(
        default=300,
        ge=10,
        description="Rate-limit sliding window duration in seconds.",
    )

    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"],
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                import json

                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        raise ValueError("CORS_ORIGINS must be a list of origins or a comma-separated string.")

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the postgresql+asyncpg:// driver scheme."
            )
        return cleaned

    @field_validator("MONGODB_URL")
    @classmethod
    def validate_mongodb_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError(
                "MONGODB_URL must use the mongodb:// or mongodb+srv:// scheme."
            )
        return cleaned

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if cleaned not in {"HS256", "HS384", "HS512"}:
            raise ValueError("JWT_ALGORITHM must be one of HS256, HS384, or HS512.")
        return cleaned


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
