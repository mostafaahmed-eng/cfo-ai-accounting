from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/cfo_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    FX_PROVIDER_BASE_URL: str = "https://open.er-api.com/v6"
    FX_PROVIDER_TIMEOUT_SECONDS: float = 10.0
    FX_AUTO_FETCH_MAX_AGE_DAYS: int = 2
    S3_ENDPOINT_URL: str = ""
    S3_PUBLIC_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_NAME: str = "cfo-documents"
    S3_REGION: str = "auto"
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""
    TELEGRAM_BOT_USERNAME: str = ""
    TELEGRAM_PAIRING_TTL_MINUTES: int = 15
    TELEGRAM_EDIT_TTL_MINUTES: int = 15
    TELEGRAM_ALLOW_INSECURE_LOCAL_WEBHOOK: bool = False
    TELEGRAM_POLLING_ENABLED: bool = False
    TELEGRAM_POLLING_INTERNAL_WEBHOOK_URL: str = ""
    TELEGRAM_POLLING_OFFSET_FILE: str = "/tmp/telegram_poll_offset"
    ENCRYPTION_KEY: str = ""
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_PDF_PAGES: int = 20
    ALLOWED_MIME_TYPES: list[str] = [
        "image/jpeg",
        "image/png",
        "application/pdf",
    ]
    CORS_ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("CORS_ALLOWED_ORIGINS", "ALLOWED_ORIGINS"),
    )
    MIN_PASSWORD_LENGTH: int = 8
    HSTS_ENABLED: bool = False
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_AI: str = "10/hour"
    RATE_LIMIT_WEBHOOK: str = "30/minute"
    ENVIRONMENT: str = "development"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        import os

        if (
            os.environ.get("ENVIRONMENT") == "production"
            and v == "change-me-in-production"
        ):
            raise ValueError("SECRET_KEY must be changed from default in production")
        return v

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        import os

        if os.environ.get("ENVIRONMENT") != "production":
            return v
        if not v:
            raise ValueError("ENCRYPTION_KEY must be set in production")
        try:
            from cryptography.fernet import Fernet

            Fernet(v.encode())
        except (ValueError, TypeError) as exc:
            raise ValueError(
                "ENCRYPTION_KEY must be a valid Fernet key "
                '(generate with: python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())")'
            ) from exc
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
