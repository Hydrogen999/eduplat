from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "EduPlat NG"
    ENV: str = "dev"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://eduplat:eduplat_dev@localhost:5432/eduplat"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 7

    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"

    FRONTEND_ORIGIN: str = "http://localhost:8000"
    MIN_AGE: int = 13
    DEFAULT_TOPIC_PRICE_KOBO: int = 200_000
    DEFAULT_EXAM_FEE_KOBO: int = 100_000
    SMTP_URL: str = ""

settings = Settings()