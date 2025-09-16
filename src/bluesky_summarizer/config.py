"""
Configuration management for the Bluesky Feed Summarizer (Turso-only).
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
    """Configuration for database connection (Turso-only, backward-compatible fields)."""

    # Legacy fields kept for compatibility with tests
    db_path: str = Field(default="./data/bluesky_feed.db")
    environment: str = Field(default="local")

    # Turso settings
    url: str = Field(
        default="", description="Turso database URL (e.g., libsql://your-db.turso.io)"
    )
    auth_token: str = Field(default="", description="Turso authentication token")

    @property
    def is_turso(self) -> bool:
        return self.environment == "production" and bool(
            self.url and self.url.startswith(("libsql://", "https://"))
        )

    @property
    def path(self) -> str:
        # legacy path behavior
        return self.db_path


class AppConfig(BaseModel):
    """Main application configuration."""

    default_days_back: int = Field(
        default=1, description="Default number of days to look back for posts"
    )
    max_posts_per_fetch: int = Field(
        default=100, description="Maximum number of posts to fetch per request"
    )
    max_prompt_chars: int = Field(
        default=20000,
        description="Hard cap on characters included in a single summarization prompt (prevents token overflow)",
    )
    api_retry_attempts: int = Field(
        default=3, description="Number of retry attempts for external API calls"
    )
    api_retry_base_delay: float = Field(
        default=0.5, description="Base delay (seconds) for external API retry backoff"
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
            db_path=os.getenv("DATABASE_PATH", "./data/bluesky_feed.db"),
            environment=os.getenv("DB_ENVIRONMENT", "local"),
            url=os.getenv("TURSO_DATABASE_URL", ""),
            auth_token=os.getenv("TURSO_AUTH_TOKEN", ""),
        )

        self.app = AppConfig(
            default_days_back=int(os.getenv("DEFAULT_DAYS_BACK", "1")),
            max_posts_per_fetch=int(os.getenv("MAX_POSTS_PER_FETCH", "100")),
            max_prompt_chars=int(os.getenv("MAX_PROMPT_CHARS", "20000")),
            api_retry_attempts=int(os.getenv("API_RETRY_ATTEMPTS", "3")),
            api_retry_base_delay=float(os.getenv("API_RETRY_BASE_DELAY", "0.5")),
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


def set_database_environment(environment: str) -> None:
    """Backward-compatible helper to set DB_ENVIRONMENT.

    Note: SQLite is no longer supported; this writes the .env key for legacy
    scripts/tests but the application will still use Turso.
    """
    if environment not in ["local", "production"]:
        raise ValueError("Environment must be either 'local' or 'production'")

    env_file = ".env"
    env_lines: list[str] = []
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            env_lines = f.readlines()

    found = False
    for i, line in enumerate(env_lines):
        if line.strip().startswith("DB_ENVIRONMENT="):
            env_lines[i] = f"DB_ENVIRONMENT={environment}\n"
            found = True
            break
    if not found:
        env_lines.append(f"DB_ENVIRONMENT={environment}\n")

    with open(env_file, "w") as f:
        f.writelines(env_lines)

    load_dotenv(override=True)
    os.environ["DB_ENVIRONMENT"] = environment


def get_database_environment() -> str:
    """Backward-compatible getter for DB_ENVIRONMENT (default 'local')."""
    # Do not implicitly load .env here to avoid picking up parent project values
    # when tests intentionally expect a default of 'local'.
    return os.getenv("DB_ENVIRONMENT", "local")


# For backwards compatibility, create a lazy config object
class LazyConfig:
    def __init__(self):
        self._config = None

    def __getattr__(self, name):
        if self._config is None:
            self._config = Config()
        return getattr(self._config, name)


config = LazyConfig()
