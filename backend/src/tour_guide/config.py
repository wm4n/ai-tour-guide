"""Configuration for the Tour Guide backend."""

from pydantic import Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables."""

    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    host: str = Field("0.0.0.0", alias="HOST")  # noqa: S104
    port: int = Field(8000, alias="PORT")
    poi_cache_dir: str = Field(
        "/tmp/tour_guide_cache",  # noqa: S108
        alias="POI_CACHE_DIR",
    )
    narration_cache_dir: str = Field(
        "/tmp/tour_guide_narration_cache",  # noqa: S108
        alias="NARRATION_CACHE_DIR",
    )
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    model_config = {"populate_by_name": True, "env_prefix": ""}
