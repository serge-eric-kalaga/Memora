from typing import Type, Literal
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource


class SETTINGS(BaseSettings):
    INITIALISE_DATABASE: bool = True
    APP_NAME: str
    ADMINS_EMAIL: str
    SECRET_KEY: str
    JWT_SECRET: str
    ALGORITHM: str
    DATABASE_URL: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 31536000
    GOOGLE_API_KEY: str | None = None
    REDIS_DATABASE_URL: str | None = None  # Ancien nom conservé pour compatibilité.
    REDIS_URL: str | None = None
    REDIS_PREFIX: str = "fullstack:dev:v1"
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_GLOBAL_LIMIT: int = Field(default=300, ge=0)
    RATE_LIMIT_GLOBAL_WINDOW_SECONDS: int = Field(default=60, ge=1)
    RATE_LIMIT_FAIL_CLOSED: bool = True
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = Field(default=60, gt=0)
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    S3_BUCKET: str = ""
    S3_ENDPOINT_URL: str = ""
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_ADDRESSING_STYLE: Literal["auto", "path", "virtual"] = "auto"
    PROFILE_PHOTO_DIR: Path = Path("static/uploads/profile_photos")
    PROFILE_PHOTO_MAX_BYTES: int = Field(default=5 * 1024 * 1024, gt=0)
    PROFILE_PHOTO_MAX_PIXELS: int = Field(default=16_000_000, gt=0)
    FRONTEND_URL: str = "http://localhost:3000"
    PASSWORD_RESET_EXPIRE_MINUTES: int = Field(default=30, ge=1, le=120)
    PASSWORD_RESET_WINDOW_SECONDS: int = Field(default=900, ge=60, le=86400)
    PASSWORD_RESET_EMAIL_LIMIT: int = Field(default=3, ge=1)
    PASSWORD_RESET_IP_LIMIT: int = Field(default=30, ge=1)
    EMAIL_VERIFICATION_ENABLED: bool = False
    EMAIL_VERIFICATION_EXPIRE_MINUTES: int = Field(default=60, ge=1, le=1440)
    EMAIL_VERIFICATION_WINDOW_SECONDS: int = Field(default=900, ge=60, le=86400)
    EMAIL_VERIFICATION_EMAIL_LIMIT: int = Field(default=3, ge=1)
    EMAIL_VERIFICATION_IP_LIMIT: int = Field(default=30, ge=1)
    EMAIL_HOST: str | None = None
    EMAIL_DOMAIN: str | None = None
    EMAIL_PORT: str | None = None
    EMAIL_USERNAME: str | None = None
    EMAIL_PASSWORD: str | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return dotenv_settings, env_settings, file_secret_settings, init_settings


# Settings for production
Setting: SETTINGS | None = SETTINGS()
