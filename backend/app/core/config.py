from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str = "dev-api-key-change-me"
    tenant_id: str = "00000000-0000-0000-0000-000000000001"
    log_level: str = "INFO"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5434
    postgres_user: str = "taskforge"
    postgres_password: str = "taskforge"
    postgres_db: str = "taskforge"
    database_url: str = "postgresql+asyncpg://taskforge:taskforge@localhost:5434/taskforge"

    # Redis
    redis_url: str = "redis://localhost:6381/0"

    # Worker (used in later blocks)
    worker_id: str = ""
    worker_concurrency: int = 10
    worker_queues: str = "default,emails"
    lease_duration_seconds: int = 60
    heartbeat_interval_seconds: int = 20
    recovery_scan_interval_seconds: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
