from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    database_url: str = "postgresql+asyncpg://taskpilot:taskpilot@localhost:5432/taskpilot"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "development-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cors_origins: str = "http://localhost:3000"
    storage_endpoint: str = "http://localhost:9000"
    storage_public_endpoint: str | None = None
    storage_bucket: str = "taskpilot"
    storage_key: str = "taskpilot"
    storage_secret: str = "taskpilot-dev-password"
    storage_region: str = "us-east-1"
    storage_max_file_bytes: int = 20 * 1024 * 1024
    storage_workspace_quota_bytes: int = 2 * 1024 * 1024 * 1024
    storage_presign_seconds: int = 300
    storage_sse: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
