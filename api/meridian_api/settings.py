from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://meridian:meridian@localhost:5432/meridian"
    baseline_trailing_days: int = 28
    baseline_cache_seconds: int = 900
