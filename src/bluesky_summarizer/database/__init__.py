"""Database layer for the Bluesky Feed Summarizer.

Provides a backend-agnostic database interface via
:class:`~.base.AbstractDatabaseManager`.  Consumers should use the
:func:`~.factory.create_database_manager` factory to obtain a manager
from a standard connection URL (SQLite, PostgreSQL, MySQL, etc.).

For backward compatibility the legacy :class:`~.operations.DatabaseManager`
class is still exported and accepts a plain SQLite file path.
"""

from .models import Post, Summary
from .base import AbstractDatabaseManager
from .operations import DatabaseManager
from .sqlalchemy_manager import SQLAlchemyDatabaseManager
from .factory import create_database_manager, create_database_manager_from_path

__all__ = [
    "Post",
    "Summary",
    "AbstractDatabaseManager",
    "DatabaseManager",
    "SQLAlchemyDatabaseManager",
    "create_database_manager",
    "create_database_manager_from_path",
]
