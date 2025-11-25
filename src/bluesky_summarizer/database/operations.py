"""
Database operations for SQLite integration.
"""

from __future__ import annotations

import sqlite3
import datetime as dt
from typing import List, Optional, Any, Tuple
from pathlib import Path
from .models import Post, Summary


class DatabaseManager:
    """SQLite database manager for posts & summaries."""

    def __init__(self, db_path: str, **kwargs: Any) -> None:
        self.db_path = db_path
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Metadata table for schema versioning
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            # Posts table
            cursor.execute(
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
            cursor.execute(
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
                cursor.execute(index_sql)

            # Insert metadata if not present
            cursor.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('schema_version', '1')"
            )
            cursor.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('last_stream_cursor', '')"
            )
            cursor.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('last_stream_time', '')"
            )
            conn.commit()

    def save_post(self, post: Post) -> int:
        """Save a post to the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO posts
                (uri, cid, author_handle, author_did, text, created_at, 
                 like_count, repost_count, reply_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uri) DO UPDATE SET
                    cid=excluded.cid,
                    author_handle=excluded.author_handle,
                    author_did=excluded.author_did,
                    text=excluded.text,
                    created_at=excluded.created_at,
                    like_count=excluded.like_count,
                    repost_count=excluded.repost_count,
                    reply_count=excluded.reply_count,
                    indexed_at=CURRENT_TIMESTAMP
                """,
                (
                    post.uri,
                    post.cid,
                    post.author_handle,
                    post.author_did,
                    post.text,
                    post.created_at.isoformat(),
                    post.like_count,
                    post.repost_count,
                    post.reply_count,
                ),
            )
            return cursor.lastrowid or 0

    def save_posts(self, posts: List[Post]) -> dict:
        """
        Save multiple Post objects to the database in a single batch operation.
        """
        if not posts:
            return {"new": 0, "updated": 0, "total": 0}

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Identify existing URIs to calculate stats
            uris = [p.uri for p in posts]
            # Chunk the check if too many posts to avoid SQL variable limit
            existing_uris = set()
            chunk_size = 900
            for i in range(0, len(uris), chunk_size):
                chunk = uris[i : i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                cursor.execute(
                    f"SELECT uri FROM posts WHERE uri IN ({placeholders})", chunk
                )
                existing_uris.update(row[0] for row in cursor.fetchall())

            new_count = 0
            updated_count = 0

            for post in posts:
                if post.uri in existing_uris:
                    updated_count += 1
                else:
                    new_count += 1

            # 2. Perform Upsert
            cursor.executemany(
                """
                INSERT INTO posts
                (uri, cid, author_handle, author_did, text, created_at,
                    like_count, repost_count, reply_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uri) DO UPDATE SET
                    cid=excluded.cid,
                    author_handle=excluded.author_handle,
                    author_did=excluded.author_did,
                    text=excluded.text,
                    created_at=excluded.created_at,
                    like_count=excluded.like_count,
                    repost_count=excluded.repost_count,
                    reply_count=excluded.reply_count,
                    indexed_at=CURRENT_TIMESTAMP
                """,
                [
                    (
                        post.uri,
                        post.cid,
                        post.author_handle,
                        post.author_did,
                        post.text,
                        post.created_at.isoformat(),
                        post.like_count,
                        post.repost_count,
                        post.reply_count,
                    )
                    for post in posts
                ],
            )
            conn.commit()
            return {"new": new_count, "updated": updated_count, "total": len(posts)}

    def get_posts_by_date_range(
        self, start_date: dt.datetime, end_date: dt.datetime
    ) -> List[Post]:
        """Get posts within a date range."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT uri, cid, author_handle, author_did, text, created_at,
                       like_count, repost_count, reply_count
                FROM posts
                WHERE created_at >= ? AND created_at <= ?
                ORDER BY created_at ASC
                """,
                (start_date.isoformat(), end_date.isoformat()),
            )

            posts = []
            for row in cursor.fetchall():
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
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if start_date and end_date:
                cursor.execute(
                    """
                    SELECT uri, cid, author_handle, author_did, text, created_at,
                           like_count, repost_count, reply_count
                    FROM posts
                    WHERE author_handle = ? AND created_at >= ? AND created_at <= ?
                    ORDER BY created_at ASC
                    """,
                    (author_handle, start_date.isoformat(), end_date.isoformat()),
                )
            else:
                cursor.execute(
                    """
                    SELECT uri, cid, author_handle, author_did, text, created_at,
                           like_count, repost_count, reply_count
                    FROM posts
                    WHERE author_handle = ?
                    ORDER BY created_at ASC
                    """,
                    (author_handle,),
                )

            posts = []
            for row in cursor.fetchall():
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
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO summaries
                (start_date, end_date, post_count, summary_text, model_used)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    summary.start_date.isoformat(),
                    summary.end_date.isoformat(),
                    summary.post_count,
                    summary.summary_text,
                    summary.model_used,
                ),
            )
            return cursor.lastrowid or 0

    def get_summary_by_date_range(
        self, start_date: dt.datetime, end_date: dt.datetime
    ) -> Optional[Summary]:
        """Get a summary for a specific date range."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT start_date, end_date, post_count, summary_text, model_used, created_at
                FROM summaries
                WHERE start_date <= ? AND end_date >= ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (start_date.isoformat(), end_date.isoformat()),
            )

            row = cursor.fetchone()
            if not row:
                return None

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
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT start_date, end_date, post_count, summary_text, model_used, created_at
                FROM summaries
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )

            summaries = []
            for row in cursor.fetchall():
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
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if start_date and end_date:
                cursor.execute(
                    "SELECT COUNT(*) FROM posts WHERE created_at >= ? AND created_at <= ?",
                    (start_date.isoformat(), end_date.isoformat()),
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM posts")

            row = cursor.fetchone()
            return row[0] if row else 0

    def delete_old_posts(self, cutoff_date: dt.datetime) -> int:
        """Delete posts older than the cutoff date."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM posts WHERE created_at < ?", (cutoff_date.isoformat(),)
            )
            return cursor.rowcount

    def set_metadata(self, key: str, value: str) -> None:
        """Set a metadata value."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()

    def get_metadata(self, key: str) -> Optional[str]:
        """Get a metadata value."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM metadata WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def close(self) -> None:
        """Close the database connection."""
        # SQLite connections are closed automatically when using context manager,
        # but we might want to keep one open if we weren't using context managers for everything.
        # In this implementation, we open/close per operation, so this is a no-op.
        pass

    # Compatibility helper methods
    def get_latest_summary(self) -> Optional[Summary]:
        """Return the most recent summary or None."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT start_date, end_date, post_count, summary_text, model_used, created_at
                FROM summaries
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if not row:
                return None

            return Summary(
                start_date=dt.datetime.fromisoformat(row[0]),
                end_date=dt.datetime.fromisoformat(row[1]),
                post_count=row[2],
                summary_text=row[3],
                model_used=row[4],
                created_at=dt.datetime.fromisoformat(row[5]),
            )

    def get_total_post_count(self) -> int:
        return self.get_post_count()

    def get_unique_uri_count(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT uri) FROM posts")
            row = cursor.fetchone()
            return row[0] if row else 0

    def find_duplicate_uris(self) -> List[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT uri FROM posts GROUP BY uri HAVING COUNT(*) > 1
                """
            )
            return [row[0] for row in cursor.fetchall()]

    def get_posts_with_duplicate_content(self) -> List[Tuple[str, int]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT text, COUNT(*) as cnt FROM posts GROUP BY text HAVING cnt > 1
                """
            )
            return [(row[0], row[1]) for row in cursor.fetchall()]

    def get_duplicate_content_count(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT text, COUNT(*) as cnt FROM posts GROUP BY text HAVING cnt > 1
                )
                """
            )
            row = cursor.fetchone()
            return row[0] if row else 0


__all__ = ["DatabaseManager"]
