from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    model_name: str = "gpt-5-mini"
    model_temperature: float = Field(default=0.1, ge=0.0, le=2.0)

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_tracing_environment: str = "development"

    checkpoint_backend: str = "memory"
    output_dir: Path = Path("./outputs")
    max_pdf_mb: int = Field(default=50, gt=0)
    max_chunk_chars: int = Field(default=12000, gt=1000)
    max_slides: int = Field(default=30, ge=3, le=100)
    default_template_path: Path | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
