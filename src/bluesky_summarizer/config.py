"""
Configuration management for the Bluesky Feed Summarizer.
"""

import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class BlueskyConfig(BaseModel):
    """Configuration for Bluesky API."""

    handle: str = Field(..., description="Bluesky handle (e.g., user.bsky.social)")
    password: str = Field(..., description="Bluesky app password")


class AnthropicConfig(BaseModel):
    """Configuration for Anthropic Claude API."""

    api_key: str = Field(..., description="Anthropic API key")


class DatabaseConfig(BaseModel):
    """Configuration for SQLite database."""

    path: str = Field(
        default="./data/bluesky_feed.db", description="Path to SQLite database file"
    )


class AppConfig(BaseModel):
    """Main application configuration."""

    default_days_back: int = Field(
        default=1, description="Default number of days to look back for posts"
    )
    max_posts_per_fetch: int = Field(
        default=100, description="Maximum number of posts to fetch per request"
    )


class Config:
    """Main configuration class that loads all settings."""

    def __init__(self):
        self.bluesky = BlueskyConfig(
            handle=self._get_env_var("BLUESKY_HANDLE"),
            password=self._get_env_var("BLUESKY_PASSWORD"),
        )

        self.anthropic = AnthropicConfig(api_key=self._get_env_var("ANTHROPIC_API_KEY"))

        self.database = DatabaseConfig(
            path=os.getenv("DATABASE_PATH", "./data/bluesky_feed.db")
        )

        self.app = AppConfig(
            default_days_back=int(os.getenv("DEFAULT_DAYS_BACK", "1")),
            max_posts_per_fetch=int(os.getenv("MAX_POSTS_PER_FETCH", "100")),
        )

    def _get_env_var(self, var_name: str) -> str:
        """Get environment variable or raise error if not found."""
        value = os.getenv(var_name)
        if value is None:
            raise ValueError(f"Environment variable {var_name} is required but not set")
        return value


def get_config() -> Config:
    """Get the application configuration."""
    return Config()


# For backwards compatibility, create a lazy config object
class LazyConfig:
    def __init__(self):
        self._config = None

    def __getattr__(self, name):
        if self._config is None:
            self._config = Config()
        return getattr(self._config, name)


config = LazyConfig()
