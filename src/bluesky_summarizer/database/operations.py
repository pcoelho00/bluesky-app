"""Shim module for database operations (Turso-only).

SQLite support has been removed. This module provides a backward-compatible
`DatabaseManager` that delegates to `TursoDatabaseManager` from libSQL/Turso.
"""

from __future__ import annotations

import os
from typing import Any

from .turso_operations import TursoDatabaseManager


class DatabaseManager(TursoDatabaseManager):
    """Backwards-compatible alias of TursoDatabaseManager.

    Notes:
        - The old SQLite constructor accepted a file path. We accept arbitrary
          positional/keyword arguments for compatibility but ignore any
          `db_path` parameter. The connection is established using the
          environment variables `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`,
          or explicit `url`/`auth_token` if provided.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        # Prefer explicit parameters if provided
        url = kwargs.pop("url", None) or os.getenv("TURSO_DATABASE_URL", "")
        auth_token = kwargs.pop("auth_token", None) or os.getenv("TURSO_AUTH_TOKEN", "")
        super().__init__(url=url, auth_token=auth_token)

    # Compatibility helper methods expected by tests
    def get_latest_summary(self):
        """Return the most recent summary or None."""
        from .turso_operations import dt as _dt  # reuse datetime import

        result = self.client.execute(
            """
            SELECT start_date, end_date, post_count, summary_text, model_used, created_at
            FROM summaries
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        rows = getattr(result, "rows", [])
        if not rows:
            return None
        from .models import Summary  # import here to avoid cycles

        r = rows[0]
        return Summary(
            start_date=_dt.datetime.fromisoformat(r[0]),
            end_date=_dt.datetime.fromisoformat(r[1]),
            post_count=r[2],
            summary_text=r[3],
            model_used=r[4],
            created_at=_dt.datetime.fromisoformat(r[5]),
        )

    def get_total_post_count(self) -> int:
        res = self.client.execute("SELECT COUNT(*) FROM posts")
        rows = getattr(res, "rows", [])
        return rows[0][0] if rows else 0

    def get_unique_uri_count(self) -> int:
        res = self.client.execute("SELECT COUNT(DISTINCT uri) FROM posts")
        rows = getattr(res, "rows", [])
        return rows[0][0] if rows else 0

    def find_duplicate_uris(self):
        res = self.client.execute(
            """
            SELECT uri FROM posts GROUP BY uri HAVING COUNT(*) > 1
            """
        )
        return [row[0] for row in getattr(res, "rows", [])]

    def get_posts_with_duplicate_content(self):
        res = self.client.execute(
            """
            SELECT text, COUNT(*) as cnt FROM posts GROUP BY text HAVING cnt > 1
            """
        )
        return [(row[0], row[1]) for row in getattr(res, "rows", [])]

    def get_duplicate_content_count(self) -> int:
        res = self.client.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT text, COUNT(*) as cnt FROM posts GROUP BY text HAVING cnt > 1
            )
            """
        )
        rows = getattr(res, "rows", [])
        return rows[0][0] if rows else 0


__all__ = ["DatabaseManager"]
