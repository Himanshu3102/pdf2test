import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Exam Practice App"
    DEBUG: bool = False
    DATABASE_URL: str = "sqlite:///./data/exam_app.db"
    STORAGE_DIR: str = "./data/uploads"
    MAX_UPLOAD_MB: int = 25
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    # Google Gemini (OpenAI-compatible endpoint)
    GEMINI_API_KEY: str | None = None
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    # OpenCode Go (OpenAI-compatible)
    OPENCODE_GO_API_KEY: str | None = None
    OPENCODE_GO_BASE_URL: str = "https://opencode.ai/zen/go/v1"
    OPENCODE_GO_MODEL: str | None = None
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_MAX_INPUT_CHARS: int = 40000
    LLM_MAX_OUTPUT_TOKENS: int = 8192
    CHAT_RATE_LIMIT: str = "20/minute"
    UPLOAD_RATE_LIMIT: str = "10/minute"
    # Cloudflare R2 / S3-compatible object storage (optional; falls back to local disk)
    R2_ACCOUNT_ID: str | None = None
    R2_ACCESS_KEY_ID: str | None = None
    R2_SECRET_ACCESS_KEY: str | None = None
    R2_BUCKET: str | None = None
    R2_ENDPOINT_URL: str | None = None
    # Auth
    AUTH_SECRET_KEY: str = "dev-secret-change-me-in-production"
    AUTH_TOKEN_TTL_DAYS: int = 30
    OCR_ENABLED: bool = True
    DEFAULT_CORRECT_POINTS: float = 4.0
    DEFAULT_INCORRECT_POINTS: float = -1.0
    DEFAULT_UNANSWERED_POINTS: float = 0.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
