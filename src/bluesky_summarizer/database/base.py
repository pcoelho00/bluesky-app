"""
Abstract base class for database managers.

All database backends (SQLite, PostgreSQL, MySQL, etc.) must implement
this interface, ensuring consumers can swap backends without code changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Tuple


from .models import Post, Summary


class AbstractDatabaseManager(ABC):
    """Abstract interface that every database backend must implement."""

    # ── Post operations ─────────────────────────────────────────────

    @abstractmethod
    def save_post(self, post: Post) -> int:
        """Upsert a single post. Returns the row id."""
        ...

    @abstractmethod
    def save_posts(self, posts: List[Post]) -> dict:
        """Batch-upsert posts. Returns ``{"new": int, "updated": int, "total": int}``."""
        ...

    @abstractmethod
    def get_posts_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> List[Post]:
        """Return posts whose ``created_at`` falls within the inclusive range."""
        ...

    @abstractmethod
    def get_posts_by_author(
        self,
        author_handle: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Post]:
        """Return posts by a given author, optionally filtered by date."""
        ...

    @abstractmethod
    def get_post_count(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Return the number of posts, optionally filtered by date range."""
        ...

    @abstractmethod
    def get_total_post_count(self) -> int:
        """Return the total number of posts in the database."""
        ...

    @abstractmethod
    def get_unique_uri_count(self) -> int:
        """Return the count of distinct post URIs."""
        ...

    @abstractmethod
    def find_duplicate_uris(self) -> List[str]:
        """Return URIs that appear more than once (should be empty with constraints)."""
        ...

    @abstractmethod
    def get_posts_with_duplicate_content(self) -> List[Tuple[str, int]]:
        """Return ``(text, count)`` pairs for texts that appear more than once."""
        ...

    @abstractmethod
    def get_duplicate_content_count(self) -> int:
        """Return the number of distinct texts that have duplicates."""
        ...

    @abstractmethod
    def delete_old_posts(self, cutoff_date: datetime) -> int:
        """Delete posts older than *cutoff_date*. Returns rows deleted."""
        ...

    @abstractmethod
    def prune_posts_older_than(self, before: datetime) -> int:
        """Alias for :meth:`delete_old_posts`. Returns rows deleted."""
        ...

    # ── Summary operations ──────────────────────────────────────────

    @abstractmethod
    def save_summary(self, summary: Summary) -> int:
        """Insert a summary. Returns the row id."""
        ...

    @abstractmethod
    def get_summary_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> Optional[Summary]:
        """Return the most recent summary that overlaps the given date range."""
        ...

    @abstractmethod
    def get_recent_summaries(self, limit: int = 10) -> List[Summary]:
        """Return the *limit* most recent summaries, newest first."""
        ...

    @abstractmethod
    def get_latest_summary(self) -> Optional[Summary]:
        """Return the single most recent summary, or ``None``."""
        ...

    # ── Metadata operations ─────────────────────────────────────────

    @abstractmethod
    def set_metadata(self, key: str, value: str) -> None:
        """Set a key/value metadata pair (upsert)."""
        ...

    @abstractmethod
    def get_metadata(self, key: str) -> Optional[str]:
        """Get the value for a metadata *key*, or ``None`` if missing."""
        ...

    # ── Maintenance operations ──────────────────────────────────────

    @abstractmethod
    def vacuum(self) -> None:
        """Reclaim unused storage space (no-op on backends that don't need it)."""
        ...

    @abstractmethod
    def get_db_size_bytes(self) -> int:
        """Return the approximate database size in bytes."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release any held resources (connections, files, etc.)."""
        ...


__all__ = ["AbstractDatabaseManager"]
