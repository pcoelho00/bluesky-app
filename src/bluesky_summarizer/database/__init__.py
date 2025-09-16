"""Database operations for the Bluesky Feed Summarizer.

SQLite support was removed; Turso/libSQL is the only backend. For backwards
compatibility, `DatabaseManager` is an alias of `TursoDatabaseManager`.
"""

from .models import Post, Summary
from .turso_operations import TursoDatabaseManager
from .factory import create_database_manager
from .operations import DatabaseManager

__all__ = [
    "Post",
    "Summary",
    "DatabaseManager",
    "TursoDatabaseManager",
    "create_database_manager",
]
