from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://callcenter:callcenter123@localhost:5432/callcenter"
    SYNC_DATABASE_URL: str = "postgresql://callcenter:callcenter123@localhost:5432/callcenter"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "your-super-secret-key-change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Sarvam AI
    SARVAM_API_KEY: str = ""
    DEFAULT_SARVAM_VOICE: str = "meera"
    DEFAULT_SARVAM_TTS_MODEL: str = "bulbul:v2"

    # Google Gemini
    GEMINI_API_KEY: str = ""

    # Exotel
    EXOTEL_SID: str = ""
    EXOTEL_API_KEY: str = ""
    EXOTEL_API_TOKEN: str = ""
    EXOTEL_SUBDOMAIN: str = ""

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = "ai-call-center-audio"
    AWS_REGION: str = "ap-south-1"

    # App
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
