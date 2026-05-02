from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://engram:engram@localhost:5432/engram"

    # Redis (Celery broker)
    redis_url: str = "redis://localhost:6379/0"

    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/api/auth/callback"

    # Frontend URL (for post-auth redirect)
    frontend_url: str = "http://localhost:3000"

    # LLM (D45: configurable provider — "gemini" or "anthropic")
    llm_provider: str = "gemini"  # "gemini" | "anthropic"
    llm_model: str = "gemini-2.5-flash"

    # Gemini (free tier)
    google_api_key: str = ""

    # Anthropic (paid — set llm_provider=anthropic to use)
    anthropic_api_key: str = ""

    # Notion OAuth
    notion_client_id: str = ""
    notion_client_secret: str = ""
    notion_redirect_uri: str = "http://localhost:8000/api/providers/notion/callback"

    # Embeddings (D44: local model via sentence-transformers)
    embedding_model: str = "nomic-ai/nomic-embed-text-v1.5"
    embedding_dimension: int = 768

    # CORS — accepts a comma-separated string from env (e.g. for backend host)
    # OR a JSON list. NoDecode skips pydantic-settings' default JSON
    # auto-decode so the raw env string reaches the validator below.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, v: object) -> object:
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                import json

                return json.loads(stripped)
            if stripped == "":
                return []
            return [s.strip() for s in stripped.split(",") if s.strip()]
        return v

    # Logging / observability
    log_level: str = "INFO"
    sentry_dsn: str = ""

    # Debug-only endpoints (e.g. provider disconnect for re-OAuth testing)
    engram_debug_endpoints: bool = False

    model_config = {
        "env_file": ["../.env", ".env"],  # check repo root first, then backend/
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # ignore unknown env vars (e.g. NEXT_PUBLIC_*)
    }


settings = Settings()
