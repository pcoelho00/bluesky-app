"""Database factory for creating the appropriate database manager."""

from __future__ import annotations

from ..config import DatabaseConfig
from .operations import DatabaseManager
from .turso_operations import TursoDatabaseManager


def create_database_manager(config: DatabaseConfig):
    """Create the appropriate database manager based on configuration.

    Args:
        config: Database configuration object

    Returns:
        Either a DatabaseManager (for local SQLite) or TursoDatabaseManager (for Turso)
    """
    if config.is_turso:
        if not config.url or not config.auth_token:
            raise ValueError(
                "Production database environment is configured but missing credentials.\n"
                "Please set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN environment variables.\n"
                "Or switch to local environment with: python -m bluesky_summarizer db switch local"
            )
        return TursoDatabaseManager(config.url, config.auth_token)
    else:
        return DatabaseManager(config.path)
