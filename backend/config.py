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

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Notion
    notion_api_key: str = ""

    # Embeddings
    voyage_api_key: str = ""
    embedding_model: str = "voyage-code-3"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
