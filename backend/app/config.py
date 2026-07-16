from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./siraj.db"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""  # Secondary provider (optional)
    JWT_SECRET: str = "supersecretkeyforsirajmvp2026!healthcheckdashboard"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # AI Provider Configuration
    AI_PRIMARY_MODEL: str = "gemini-3.5-flash"
    AI_SECONDARY_MODEL: str = "gpt-4.1-mini"  # Used only if OPENAI_API_KEY is set
    AI_RETRY_MAX: int = 3
    AI_RETRY_BASE_DELAY: float = 1.0  # seconds
    AI_REQUEST_TIMEOUT: int = 30  # seconds
    AI_CONTEXT_CACHE_TTL: int = 300  # 5 minutes

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
