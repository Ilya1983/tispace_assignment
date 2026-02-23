from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Internal — defaults match docker-compose dev environment
    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/articles"
    database_url_sync: str = "postgresql://postgres:postgres@postgres:5432/articles"
    redis_url: str = "redis://redis:6379/0"

    # Secrets — no defaults, app fails fast if missing
    anthropic_api_key: str
    marketaux_api_token: str

    # Tunable — sensible defaults, overridable at runtime
    fetch_keyword: str = "markets"
    fetch_interval_hours: int = 6
    summary_cache_ttl: int = 86400


settings = Settings()
