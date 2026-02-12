"""
Legacy SQLite database manager.

This module preserves the original ``DatabaseManager(db_path)`` constructor
signature for backward compatibility. Internally it delegates to
:class:`~.sqlalchemy_manager.SQLAlchemyDatabaseManager` via a SQLite
connection URL so the behaviour is identical.

New code should prefer :func:`~.factory.create_database_manager` with a
standard connection URL.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, List, Optional, Tuple

from .base import AbstractDatabaseManager
from .sqlalchemy_manager import SQLAlchemyDatabaseManager
from .models import Post, Summary


class DatabaseManager(AbstractDatabaseManager):
    """SQLite database manager that wraps the SQLAlchemy backend.

    Accepts the legacy ``db_path`` string and translates it to a SQLite URL.
    All methods are forwarded to the underlying
    :class:`SQLAlchemyDatabaseManager`.
    """

    def __init__(self, db_path: str, **kwargs: Any) -> None:
        self.db_path = db_path
        connection_url = f"sqlite:///{db_path}"
        self._delegate = SQLAlchemyDatabaseManager(connection_url, **kwargs)

    # ── Post operations ─────────────────────────────────────────────

    def save_post(self, post: Post) -> int:
        return self._delegate.save_post(post)

    def save_posts(self, posts: List[Post]) -> dict:
        return self._delegate.save_posts(posts)

    def get_posts_by_date_range(
        self, start_date: dt.datetime, end_date: dt.datetime
    ) -> List[Post]:
        return self._delegate.get_posts_by_date_range(start_date, end_date)

    def get_posts_by_author(
        self,
        author_handle: str,
        start_date: Optional[dt.datetime] = None,
        end_date: Optional[dt.datetime] = None,
    ) -> List[Post]:
        return self._delegate.get_posts_by_author(author_handle, start_date, end_date)

    def get_post_count(
        self,
        start_date: Optional[dt.datetime] = None,
        end_date: Optional[dt.datetime] = None,
    ) -> int:
        return self._delegate.get_post_count(start_date, end_date)

    def get_total_post_count(self) -> int:
        return self._delegate.get_total_post_count()

    def get_unique_uri_count(self) -> int:
        return self._delegate.get_unique_uri_count()

    def find_duplicate_uris(self) -> List[str]:
        return self._delegate.find_duplicate_uris()

    def get_posts_with_duplicate_content(self) -> List[Tuple[str, int]]:
        return self._delegate.get_posts_with_duplicate_content()

    def get_duplicate_content_count(self) -> int:
        return self._delegate.get_duplicate_content_count()

    def delete_old_posts(self, cutoff_date: dt.datetime) -> int:
        return self._delegate.delete_old_posts(cutoff_date)

    def prune_posts_older_than(self, before: dt.datetime) -> int:
        return self._delegate.prune_posts_older_than(before)

    # ── Summary operations ──────────────────────────────────────────

    def save_summary(self, summary: Summary) -> int:
        return self._delegate.save_summary(summary)

    def get_summary_by_date_range(
        self, start_date: dt.datetime, end_date: dt.datetime
    ) -> Optional[Summary]:
        return self._delegate.get_summary_by_date_range(start_date, end_date)

    def get_recent_summaries(self, limit: int = 10) -> List[Summary]:
        return self._delegate.get_recent_summaries(limit)

    def get_latest_summary(self) -> Optional[Summary]:
        return self._delegate.get_latest_summary()

    # ── Metadata operations ─────────────────────────────────────────

    def set_metadata(self, key: str, value: str) -> None:
        return self._delegate.set_metadata(key, value)

    def get_metadata(self, key: str) -> Optional[str]:
        return self._delegate.get_metadata(key)

    # ── Maintenance operations ──────────────────────────────────────

    def vacuum(self) -> None:
        return self._delegate.vacuum()

    def get_db_size_bytes(self) -> int:
        return self._delegate.get_db_size_bytes()

    def close(self) -> None:
        return self._delegate.close()


__all__ = ["DatabaseManager"]
