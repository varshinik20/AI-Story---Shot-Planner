from functools import lru_cache
from typing import Any, Literal
from urllib.parse import unquote, urlsplit

from pydantic import Field, field_validator, model_validator
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
    DB_ECHO: bool = Field(
        default=False,
        description="Log every SQL statement. Independent of DEBUG; keep off except when debugging queries.",
    )

    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key for GPT-4o story and shot-plan generation.",
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o",
        description="OpenAI model to use (gpt-4o, gpt-4-turbo, etc.).",
    )
    OPENAI_MODEL_IS_REASONING: bool | None = Field(
        default=None,
        description=(
            "Force reasoning-model request shape (no temperature, uses reasoning_effort). "
            "Leave unset to auto-detect from the model name (o1/o3/o4/gpt-5/gpt-6 families)."
        ),
    )
    OPENAI_REASONING_EFFORT: Literal["low", "medium", "high", "xhigh"] = Field(
        default="low",
        description="reasoning_effort for reasoning models. Lower is faster and cheaper.",
    )
    OPENAI_MAX_CONNECTIONS: int = Field(
        default=100,
        ge=1,
        description="Max pooled HTTP connections per process to the OpenAI API.",
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
        default="",
        description=(
            "MongoDB database name storing authorized credentials. When empty, the database "
            "in the MONGODB_URL path is used (e.g. mongodb+srv://.../ai_story), falling back "
            "to 'story_planner_auth'."
        ),
    )
    MONGODB_COLLECTION: str = Field(
        default="authorized_credentials",
        description="MongoDB collection storing the single authorized account.",
    )
    MONGODB_CONNECT_TIMEOUT_MS: int = Field(
        default=10000,
        ge=500,
        description=(
            "MongoDB connect / server-selection timeout in milliseconds. Atlas SRV lookups "
            "plus TLS handshakes need more headroom than a local server."
        ),
    )
    MONGODB_SOCKET_TIMEOUT_MS: int = Field(
        default=20000,
        ge=1000,
        description="Per-operation socket timeout in milliseconds.",
    )
    MONGODB_MAX_POOL_SIZE: int = Field(
        default=100,
        ge=1,
        description="Maximum concurrent connections per backend process to MongoDB.",
    )
    MONGODB_MIN_POOL_SIZE: int = Field(
        default=0,
        ge=0,
        description="Warm connections kept open per backend process.",
    )
    MONGODB_MAX_IDLE_TIME_MS: int = Field(
        default=300000,
        ge=1000,
        description="Close pooled connections idle longer than this (milliseconds).",
    )
    MONGODB_STARTUP_VALIDATION_ENABLED: bool = Field(
        default=True,
        description=(
            "Verify MongoDB reachability and bootstrap the authorized account on startup. "
            "May only be disabled outside production (local development without MongoDB)."
        ),
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

    @model_validator(mode="after")
    def resolve_mongodb_database(self) -> "Settings":
        """Derive the auth database from the URI path when MONGODB_DATABASE is not set."""
        if self.MONGODB_MIN_POOL_SIZE > self.MONGODB_MAX_POOL_SIZE:
            raise ValueError("MONGODB_MIN_POOL_SIZE cannot exceed MONGODB_MAX_POOL_SIZE.")
        if not self.MONGODB_DATABASE.strip():
            # urlsplit performs no DNS resolution, so this is safe for mongodb+srv URIs.
            path_db = unquote(urlsplit(self.MONGODB_URL).path.lstrip("/")).strip()
            self.MONGODB_DATABASE = path_db or "story_planner_auth"
        else:
            self.MONGODB_DATABASE = self.MONGODB_DATABASE.strip()
        return self

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
