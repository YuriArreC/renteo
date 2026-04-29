"""Application settings loaded from environment.

Secrets (Supabase keys, KMS ARNs, SII provider tokens) live outside the repo.
Use .env.example as the source of truth for required keys.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_version: str = "0.0.0"
    environment: Literal["local", "preview", "staging", "production"] = "local"

    supabase_url: str = Field(default="")
    supabase_jwks_url: str = Field(default="")
    supabase_jwt_audience: str = Field(default="authenticated")

    database_url: str = Field(default="")

    redis_url: str = Field(default="")

    aws_region: str = "sa-east-1"
    kms_certs_key_arn: str = Field(default="")
    s3_certs_bucket: str = Field(default="")

    sii_provider_primary: Literal["simpleapi", "baseapi", "apigateway"] = "simpleapi"
    sii_provider_backup: Literal["simpleapi", "baseapi", "apigateway"] = "baseapi"

    sentry_dsn: str = Field(default="")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
