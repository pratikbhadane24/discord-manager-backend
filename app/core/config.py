"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Settings
    APP_NAME: str = "Discord Manager Backend"
    APP_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"

    # Database Configuration
    DATABASE_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "discord_manager"

    # JWT Configuration
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Discord OAuth2 Configuration
    DISCORD_CLIENT_ID: str = ""
    DISCORD_CLIENT_SECRET: str = ""
    DISCORD_BOT_TOKEN: str = ""
    DISCORD_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/discord/callback"
    DISCORD_API_BASE_URL: str = "https://discord.com/api/v10"

    # Webhook Security
    WEBHOOK_SECRET: str = ""


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
