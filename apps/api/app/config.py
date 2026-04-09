from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: str
    supabase_storage_bucket: str = "resumes"
    run_secret_encryption_key: str = ""
    cors_origin: str = "https://findyourjob-lusmh75vq-ericyaos-projects.vercel.app"
    cors_origin_alt: str = "http://127.0.0.1:3000"
    cors_extra_origins: str = ""
    cors_origin_regex: str = r"https://.*\.vercel\.app"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
