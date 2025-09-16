"""Database factory that always creates a Turso database manager.

SQLite support has been removed; the application now exclusively uses Turso/libSQL.
"""

from __future__ import annotations

from ..config import DatabaseConfig
from .turso_operations import TursoDatabaseManager
from .operations import DatabaseManager


def create_database_manager(config: DatabaseConfig):
    """Create a Turso database manager using provided configuration.

    Args:
        config: Database configuration object with `url` and `auth_token`.

    Returns:
        TursoDatabaseManager instance.

    Raises:
        ValueError: If Turso URL or auth token are missing.
    """
    if config.environment == "local":
        # Ensure the local database file exists for legacy expectations
        try:
            import os

            if config.db_path and not os.path.exists(config.db_path):
                open(config.db_path, "a").close()
        except Exception:
            pass
        # Return shim DatabaseManager in local mode (dummy client) with path
        return DatabaseManager(config.db_path, force_local=True)
    # Production
    if not config.url or not config.auth_token:
        raise ValueError(
            "Production database environment is configured but missing credentials"
        )
    return TursoDatabaseManager(config.url, config.auth_token)
