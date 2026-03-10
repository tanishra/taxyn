from pydantic_settings import BaseSettings

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

    class Config:
        env_file = ".env"


settings = Settings()