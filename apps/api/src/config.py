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

    # Lista separada por comas (env: CORS_ALLOWED_ORIGINS). Vacío = sin
    # CORS habilitado (las requests cross-origin fallarán con 403 del
    # browser, lo que es seguro por default).
    cors_allowed_origins: str = Field(default="http://localhost:3000")

    # Skill 11 panel admin: solo estos emails pueden gestionar reglas
    # globales. Default = los placeholder seedeados en track 11; en prod
    # se setea con los emails reales del staff Renteo.
    internal_admin_emails: str = Field(
        default=(
            "contador-socio@renteo.local,admin-tecnico@renteo.local"
        )
    )

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def internal_admin_emails_set(self) -> frozenset[str]:
        return frozenset(
            e.strip().lower()
            for e in self.internal_admin_emails.split(",")
            if e.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
