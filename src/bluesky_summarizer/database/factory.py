"""
Database manager factory.

Use :func:`create_database_manager` to obtain a backend-agnostic
:class:`~.base.AbstractDatabaseManager` from a connection URL string.

Supported URL schemes
---------------------
* ``sqlite:///path/to/db.db`` -- local SQLite file
* ``sqlite:///:memory:`` -- in-memory SQLite (useful for tests)
* ``postgresql://user:pass@host/dbname`` -- PostgreSQL
* ``postgresql+psycopg2://...`` -- PostgreSQL via psycopg2
* ``mysql+pymysql://user:pass@host/dbname`` -- MySQL / MariaDB

Any URL dialect supported by SQLAlchemy will work as long as the
corresponding driver package is installed.
"""

from __future__ import annotations

from .base import AbstractDatabaseManager
from .sqlalchemy_manager import SQLAlchemyDatabaseManager


def create_database_manager(connection_url: str, **kwargs) -> AbstractDatabaseManager:
    """Create and return a database manager for the given *connection_url*.

    Parameters
    ----------
    connection_url:
        A SQLAlchemy-compatible database URL.
    **kwargs:
        Extra keyword arguments forwarded to the backend constructor
        (e.g. ``pool_size``, ``echo``).

    Returns
    -------
    AbstractDatabaseManager
        A fully initialised database manager ready for use.

    Examples
    --------
    >>> db = create_database_manager("sqlite:///./data/app.db")
    >>> db = create_database_manager("postgresql://user:pw@localhost/mydb")
    """
    return SQLAlchemyDatabaseManager(connection_url, **kwargs)


def create_database_manager_from_path(db_path: str, **kwargs) -> AbstractDatabaseManager:
    """Convenience wrapper: create a SQLite manager from a file path.

    This exists for backward compatibility with code that uses plain file
    paths rather than connection URLs.
    """
    connection_url = f"sqlite:///{db_path}"
    return create_database_manager(connection_url, **kwargs)


__all__ = ["create_database_manager", "create_database_manager_from_path"]
