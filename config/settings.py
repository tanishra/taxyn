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
    MAX_UPLOAD_SIZE_MB: int = 25
    CORS_ORIGINS: str = ""
    ALLOW_PUBLIC_DEMO: bool = True

    # ─── Mail Config ───────────────────────────────────────────
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@taxyn.ai"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    SUPPORT_EMAIL: str = "tanishrajput9@gmail.com"

    # ─── Auth Config ───────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    ADMIN_EMAILS: str = ""

    @property
    def cors_origins(self) -> list[str]:
        values = [item.strip() for item in (self.CORS_ORIGINS or "").split(",")]
        return [item for item in values if item]

    class Config:
        env_file = ".env"
        extra = "ignore" # Ignore extra fields in .env instead of crashing


settings = Settings()
