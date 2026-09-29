from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime settings loaded exclusively from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "PARKWISE API"
    environment: str = "development"
    database_url: str = "sqlite:///./parkwise.db"
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=90)
    qr_token_expire_days: int = Field(default=30, ge=1, le=365)
    api_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:8501"
    model_path: Path = PROJECT_ROOT / "ml" / "artifacts" / "parking_model.pkl"
    model_feature_columns_path: Path = (
        PROJECT_ROOT / "ml" / "artifacts" / "feature_columns.json"
    )
    model_metrics_path: Path = PROJECT_ROOT / "ml" / "model_metrics.json"
    model_version: str = "random-forest-v1"
    ml_model_sha256: str | None = None
    log_level: str = "INFO"

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_cors(cls, value: str) -> str:
        origins = [item.strip() for item in value.split(",") if item.strip()]
        if "*" in origins:
            raise ValueError("Wildcard CORS origins are not allowed")
        return ",".join(origins)

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
