from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "Taxyn"
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    SECRET_KEY: str = "change-me"

    OPENAI_API_KEY : str = ""
    LLM_MODEL : str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 2048

    HUGGINGFACE_TOKEN: str = ""

    DATABASE_URL: str = ""
    REDIS_URL: str = ""

    CONFIDENCE_THRESHOLD: float = 0.85

    # ─── Mail Config ───────────────────────────────────────────
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@taxyn.ai"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"

    # ─── Auth Config ───────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore" # Ignore extra fields in .env instead of crashing


settings = Settings()
