from pydantic_settings import BaseSettings


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

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {
        "env_file": ["../.env", ".env"],  # check repo root first, then backend/
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # ignore unknown env vars (e.g. NEXT_PUBLIC_*)
    }


settings = Settings()
