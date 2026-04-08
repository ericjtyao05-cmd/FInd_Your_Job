from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: str
    supabase_storage_bucket: str = "resumes"
    run_secret_encryption_key: str = ""
    worker_poll_interval_seconds: int = 5
    playwright_headless: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = WorkerSettings()
