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


class OpenAIConfig(BaseModel):
    """Configuration for OpenAI API."""

    api_key: str = Field("", description="OpenAI API key")


class GeminiConfig(BaseModel):
    """Configuration for Gemini API."""

    api_key: str = Field("", description="Gemini API key")


class DatabaseConfig(BaseModel):
    """Configuration for database connection.

    The primary setting is ``connection_url`` -- a standard SQLAlchemy URL
    such as ``sqlite:///./data/app.db`` or ``postgresql://user:pw@host/db``.

    For backward compatibility the legacy ``db_path`` field is still
    accepted and exposed as a property.
    """

    connection_url: str = Field(
        default="sqlite:///./data/bluesky_feed.db",
        description="SQLAlchemy connection URL (sqlite, postgresql, mysql, …)",
    )

    @property
    def db_path(self) -> str:
        """Extract the file path from a ``sqlite:///`` URL.

        Returns the raw URL string for non-SQLite backends.
        """
        if self.connection_url.startswith("sqlite:///"):
            return self.connection_url.replace("sqlite:///", "")
        return self.connection_url

    @property
    def path(self) -> str:
        """Alias for :attr:`db_path` (backward compat)."""
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
        self.openai = OpenAIConfig(api_key=os.getenv("OPENAI_API_KEY", ""))
        self.gemini = GeminiConfig(api_key=os.getenv("GEMINI_API_KEY", ""))

        # Build connection URL: prefer DATABASE_URL, fall back to DATABASE_PATH
        connection_url = os.getenv("DATABASE_URL")
        if not connection_url:
            db_path = os.getenv("DATABASE_PATH", "./data/bluesky_feed.db")
            connection_url = f"sqlite:///{db_path}"

        self.database = DatabaseConfig(connection_url=connection_url)

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
    """Set the DB_ENVIRONMENT key in the ``.env`` file.

    Retained for backward compatibility with legacy scripts and tests.
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
    """Return the current ``DB_ENVIRONMENT`` value (default ``'local'``)."""
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
