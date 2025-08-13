"""Database operations for Turso (libSQL) integration.

This module provides the same interface as operations.py but uses libsql-client
for connecting to Turso databases.
"""

from __future__ import annotations

import datetime as dt
from typing import List, Optional

try:
    import libsql_client
except ImportError:
    raise ImportError(
        "libsql-client is required for Turso integration. "
        "Install it with: pip install libsql-client"
    )

from .models import Post, Summary


class TursoDatabaseManager:
    """Turso (libSQL) database manager for posts & summaries."""

    def __init__(self, url: str, auth_token: str) -> None:
        self.url = url
        self.auth_token = auth_token
        self.client = libsql_client.create_client(url=url, auth_token=auth_token)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        # Metadata table for schema versioning
        self.client.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        # Posts table
        self.client.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uri TEXT UNIQUE NOT NULL,
                cid TEXT NOT NULL,
                author_handle TEXT NOT NULL,
                author_did TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                like_count INTEGER DEFAULT 0,
                repost_count INTEGER DEFAULT 0,
                reply_count INTEGER DEFAULT 0,
                indexed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Summaries table
        self.client.execute(
            """
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                post_count INTEGER NOT NULL,
                summary_text TEXT NOT NULL,
                model_used TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_posts_author_handle ON posts(author_handle)",
            "CREATE INDEX IF NOT EXISTS idx_posts_author_created ON posts(author_handle, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_summaries_date_range ON summaries(start_date, end_date)",
        ]

        for index_sql in indexes:
            self.client.execute(index_sql)

        # Insert metadata if not present
        try:
            self.client.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('schema_version', '1')"
            )
            self.client.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('last_stream_cursor', '')"
            )
            self.client.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('last_stream_time', '')"
            )
        except Exception:
            # If INSERT OR IGNORE isn't supported, try individual inserts
            pass

    def save_post(self, post: Post) -> int:
        """Save a post to the database."""
        result = self.client.execute(
            """
            INSERT OR REPLACE INTO posts
            (uri, cid, author_handle, author_did, text, created_at, 
             like_count, repost_count, reply_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                post.uri,
                post.cid,
                post.author_handle,
                post.author_did,
                post.text,
                post.created_at.isoformat(),
                post.like_count,
                post.repost_count,
                post.reply_count,
            ],
        )
        return result.last_insert_rowid or 0

    def get_posts_by_date_range(
        self, start_date: dt.datetime, end_date: dt.datetime
    ) -> List[Post]:
        """Get posts within a date range."""
        result = self.client.execute(
            """
            SELECT uri, cid, author_handle, author_did, text, created_at,
                   like_count, repost_count, reply_count
            FROM posts
            WHERE created_at >= ? AND created_at <= ?
            ORDER BY created_at ASC
            """,
            [start_date.isoformat(), end_date.isoformat()],
        )

        posts = []
        for row in result.rows:
            posts.append(
                Post(
                    uri=row[0],
                    cid=row[1],
                    author_handle=row[2],
                    author_did=row[3],
                    text=row[4],
                    created_at=dt.datetime.fromisoformat(row[5]),
                    like_count=row[6] or 0,
                    repost_count=row[7] or 0,
                    reply_count=row[8] or 0,
                )
            )
        return posts

    def get_posts_by_author(
        self,
        author_handle: str,
        start_date: Optional[dt.datetime] = None,
        end_date: Optional[dt.datetime] = None,
    ) -> List[Post]:
        """Get posts by a specific author, optionally filtered by date range."""
        if start_date and end_date:
            result = self.client.execute(
                """
                SELECT uri, cid, author_handle, author_did, text, created_at,
                       like_count, repost_count, reply_count
                FROM posts
                WHERE author_handle = ? AND created_at >= ? AND created_at <= ?
                ORDER BY created_at ASC
                """,
                [author_handle, start_date.isoformat(), end_date.isoformat()],
            )
        else:
            result = self.client.execute(
                """
                SELECT uri, cid, author_handle, author_did, text, created_at,
                       like_count, repost_count, reply_count
                FROM posts
                WHERE author_handle = ?
                ORDER BY created_at ASC
                """,
                [author_handle],
            )

        posts = []
        for row in result.rows:
            posts.append(
                Post(
                    uri=row[0],
                    cid=row[1],
                    author_handle=row[2],
                    author_did=row[3],
                    text=row[4],
                    created_at=dt.datetime.fromisoformat(row[5]),
                    like_count=row[6] or 0,
                    repost_count=row[7] or 0,
                    reply_count=row[8] or 0,
                )
            )
        return posts

    def save_summary(self, summary: Summary) -> int:
        """Save a summary to the database."""
        result = self.client.execute(
            """
            INSERT INTO summaries
            (start_date, end_date, post_count, summary_text, model_used)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                summary.start_date.isoformat(),
                summary.end_date.isoformat(),
                summary.post_count,
                summary.summary_text,
                summary.model_used,
            ],
        )
        return result.last_insert_rowid or 0

    def get_summary_by_date_range(
        self, start_date: dt.datetime, end_date: dt.datetime
    ) -> Optional[Summary]:
        """Get a summary for a specific date range."""
        result = self.client.execute(
            """
            SELECT start_date, end_date, post_count, summary_text, model_used, created_at
            FROM summaries
            WHERE start_date <= ? AND end_date >= ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [start_date.isoformat(), end_date.isoformat()],
        )

        if not result.rows:
            return None

        row = result.rows[0]
        return Summary(
            start_date=dt.datetime.fromisoformat(row[0]),
            end_date=dt.datetime.fromisoformat(row[1]),
            post_count=row[2],
            summary_text=row[3],
            model_used=row[4],
            created_at=dt.datetime.fromisoformat(row[5]),
        )

    def get_recent_summaries(self, limit: int = 10) -> List[Summary]:
        """Get recent summaries."""
        result = self.client.execute(
            """
            SELECT start_date, end_date, post_count, summary_text, model_used, created_at
            FROM summaries
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [limit],
        )

        summaries = []
        for row in result.rows:
            summaries.append(
                Summary(
                    start_date=dt.datetime.fromisoformat(row[0]),
                    end_date=dt.datetime.fromisoformat(row[1]),
                    post_count=row[2],
                    summary_text=row[3],
                    model_used=row[4],
                    created_at=dt.datetime.fromisoformat(row[5]),
                )
            )
        return summaries

    def get_post_count(
        self,
        start_date: Optional[dt.datetime] = None,
        end_date: Optional[dt.datetime] = None,
    ) -> int:
        """Get total number of posts, optionally filtered by date range."""
        if start_date and end_date:
            result = self.client.execute(
                "SELECT COUNT(*) FROM posts WHERE created_at >= ? AND created_at <= ?",
                [start_date.isoformat(), end_date.isoformat()],
            )
        else:
            result = self.client.execute("SELECT COUNT(*) FROM posts")

        return result.rows[0][0] if result.rows else 0

    def delete_old_posts(self, cutoff_date: dt.datetime) -> int:
        """Delete posts older than the cutoff date."""
        result = self.client.execute(
            "DELETE FROM posts WHERE created_at < ?", [cutoff_date.isoformat()]
        )
        return result.rows_affected

    def set_metadata(self, key: str, value: str) -> None:
        """Set a metadata value."""
        self.client.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", [key, value]
        )

    def get_metadata(self, key: str) -> Optional[str]:
        """Get a metadata value."""
        result = self.client.execute("SELECT value FROM metadata WHERE key = ?", [key])
        return result.rows[0][0] if result.rows else None

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self.client, "close"):
            self.client.close()
