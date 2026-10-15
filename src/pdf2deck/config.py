from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    app_env: str = "development"
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    model_name: str = "gpt-5-mini"
    model_temperature: float = Field(default=0.1, ge=0.0, le=2.0)

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_tracing_environment: str = "development"

    checkpoint_backend: str = "memory"
    output_dir: Path = Path("./outputs")
    max_pdf_mb: int = Field(default=50, gt=0)
    # Reserved for services/chunking.py; the graph sends whole pages for now.
    max_chunk_chars: int = Field(default=12000, gt=1000)
    # Images smaller than this on either side (logos, bullets) are not extracted.
    min_image_px: int = Field(default=100, ge=1)
    # An image drawn on this many pages or more is decoration (headers, icons).
    repeated_image_pages: int = Field(default=3, ge=2)
    # Every extracted image is sent to the model, so this bounds the outline cost.
    max_images: int = Field(default=40, ge=0)
    max_slides: int = Field(default=30, ge=3, le=100)
    default_preferences_path: Path | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
