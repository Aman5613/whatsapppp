"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- App ---
    APP_NAME: str = "WhatsApp Bot API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # --- Database (Neon) ---
    DATABASE_URL: str  # pooled connection string for the app
    DIRECT_DATABASE_URL: str = ""  # direct string for Alembic migrations

    # --- Security ---
    SECRET_KEY: str  # JWT signing key
    ENCRYPTION_KEY: str  # Fernet key for encrypting secrets at rest

    # --- Public ---
    PUBLIC_BASE_URL: str = "http://localhost"  # used to build webhook URLs

    # --- Database pool ---
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 2
    DB_POOL_PRE_PING: bool = True

    # --- Rate limiting ---
    LOGIN_RATE_LIMIT: int = 5  # max failed login attempts per window
    LOGIN_RATE_WINDOW: int = 900  # 15 minutes in seconds
    CUSTOMER_RATE_LIMIT: int = 20  # max messages per customer per minute


# Singleton – import this everywhere
settings = Settings()
