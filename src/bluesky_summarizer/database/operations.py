"""Database operations for managing Bluesky posts and summaries.

Clean implementation with connection helper and identical public API.
"""

from __future__ import annotations

import os
import sqlite3
import datetime as dt
from typing import Any, List, Optional

from .models import Post, Summary


def adapt_date_iso(val: Any) -> Any:  # date -> ISO
    return val.isoformat()


def adapt_datetime_iso(val: Any) -> Any:  # datetime -> naive ISO
    return val.replace(tzinfo=None).isoformat()


def adapt_datetime_epoch(val: Any) -> int:  # datetime -> epoch int
    return int(val.timestamp())


sqlite3.register_adapter(dt.date, adapt_date_iso)
sqlite3.register_adapter(dt.datetime, adapt_datetime_iso)
sqlite3.register_adapter(dt.datetime, adapt_datetime_epoch)


def convert_date(val: Any) -> dt.date:
    return dt.date.fromisoformat(val.decode())


def convert_datetime(val: Any) -> dt.datetime:
    return dt.datetime.fromisoformat(val.decode())


def convert_timestamp(val: Any) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(val))


sqlite3.register_converter("date", convert_date)
sqlite3.register_converter("datetime", convert_datetime)
sqlite3.register_converter("timestamp", convert_timestamp)


class DatabaseManager:
    """SQLite database manager for posts & summaries."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._ensure_dir()
        self._init_schema()

    # Internal helpers --------------------------------------------------
    def _ensure_dir(self) -> None:
        d = os.path.dirname(self.db_path)
        if d and not os.path.exists(d):
            os.makedirs(d)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA synchronous=NORMAL;")
            cur.execute("PRAGMA foreign_keys=ON;")
            cur.execute("PRAGMA busy_timeout=5000;")
        except sqlite3.Error:
            pass
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            # Metadata table for schema versioning
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uri TEXT UNIQUE NOT NULL,
                    cid TEXT NOT NULL,
                    author_handle TEXT NOT NULL,
                    author_did TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    like_count INTEGER DEFAULT 0,
                    repost_count INTEGER DEFAULT 0,
                    reply_count INTEGER DEFAULT 0,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_date TIMESTAMP NOT NULL,
                    end_date TIMESTAMP NOT NULL,
                    post_count INTEGER NOT NULL,
                    summary_text TEXT NOT NULL,
                    model_used TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_author_handle ON posts(author_handle)"
            )
            # Composite index for author + created_at (query optimization)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_author_created ON posts(author_handle, created_at)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_summaries_date_range ON summaries(start_date, end_date)"
            )
            # Record schema version if not present
            cur.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('schema_version', '1')"
            )
            # Track last seen cursor / timestamp for streaming continuity
            cur.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('last_stream_cursor', '')"
            )
            cur.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('last_stream_time', '')"
            )
            conn.commit()

    # Post operations ---------------------------------------------------
    def save_post(self, post: Post) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO posts
                (uri, cid, author_handle, author_did, text, created_at,
                 like_count, repost_count, reply_count, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post.uri,
                    post.cid,
                    post.author_handle,
                    post.author_did,
                    post.text,
                    post.created_at,
                    post.like_count,
                    post.repost_count,
                    post.reply_count,
                    post.indexed_at,
                ),
            )
            return cur.lastrowid

    def post_exists(self, uri: str) -> bool:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM posts WHERE uri = ? LIMIT 1", (uri,))
            return cur.fetchone() is not None

    def get_existing_uris(self, uris: List[str]) -> set[str]:
        if not uris:
            return set()
        with self._connect() as conn:
            cur = conn.cursor()
            placeholders = ",".join("?" * len(uris))
            cur.execute(f"SELECT uri FROM posts WHERE uri IN ({placeholders})", uris)
            return {row[0] for row in cur.fetchall()}

    def save_posts(self, posts: List[Post]) -> dict[str, int]:
        if not posts:
            return {"new": 0, "updated": 0, "total": 0}
        existing = self.get_existing_uris([p.uri for p in posts])
        new_count = 0
        updated_count = 0
        seen: set[str] = set()
        with self._connect() as conn:
            cur = conn.cursor()
            for p in posts:
                try:
                    is_existing = p.uri in existing or p.uri in seen
                    # UPSERT preserving immutable created_at while updating mutable fields
                    cur.execute(
                        """
                        INSERT INTO posts
                        (uri, cid, author_handle, author_did, text, created_at,
                         like_count, repost_count, reply_count, indexed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(uri) DO UPDATE SET
                            cid=excluded.cid,
                            author_handle=excluded.author_handle,
                            author_did=excluded.author_did,
                            text=excluded.text,
                            like_count=excluded.like_count,
                            repost_count=excluded.repost_count,
                            reply_count=excluded.reply_count,
                            indexed_at=excluded.indexed_at
                        """,
                        (
                            p.uri,
                            p.cid,
                            p.author_handle,
                            p.author_did,
                            p.text,
                            p.created_at,
                            p.like_count,
                            p.repost_count,
                            p.reply_count,
                            p.indexed_at,
                        ),
                    )
                    if is_existing:
                        updated_count += 1
                    else:
                        new_count += 1
                    seen.add(p.uri)
                except sqlite3.Error as e:  # log & continue
                    import logging

                    logging.getLogger(__name__).error(
                        "Error saving post %s: %s", p.uri, e
                    )
            conn.commit()
        return {
            "new": new_count,
            "updated": updated_count,
            "total": new_count + updated_count,
        }

    def get_posts_by_date_range(
        self, start_date: dt.datetime, end_date: dt.datetime
    ) -> List[Post]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, uri, cid, author_handle, author_did, text, created_at,
                       like_count, repost_count, reply_count, indexed_at
                FROM posts
                WHERE created_at BETWEEN ? AND ?
                ORDER BY created_at ASC
                """,
                (start_date, end_date),
            )
            rows = cur.fetchall()
            return [
                Post(
                    id=r[0],
                    uri=r[1],
                    cid=r[2],
                    author_handle=r[3],
                    author_did=r[4],
                    text=r[5],
                    created_at=r[6],
                    like_count=r[7],
                    repost_count=r[8],
                    reply_count=r[9],
                    indexed_at=r[10],
                )
                for r in rows
            ]

    # Summary operations -------------------------------------------------
    def save_summary(self, summary: Summary) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO summaries
                (start_date, end_date, post_count, summary_text, model_used, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.start_date,
                    summary.end_date,
                    summary.post_count,
                    summary.summary_text,
                    summary.model_used,
                    summary.created_at,
                ),
            )
            return cur.lastrowid

    def get_latest_summary(self) -> Optional[Summary]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, start_date, end_date, post_count, summary_text, model_used, created_at
                FROM summaries
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                return None
            return Summary(
                id=row[0],
                start_date=row[1],
                end_date=row[2],
                post_count=row[3],
                summary_text=row[4],
                model_used=row[5],
                created_at=row[6],
            )

    def get_summaries_by_date_range(
        self, start_date: dt.datetime, end_date: dt.datetime
    ) -> List[Summary]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, start_date, end_date, post_count, summary_text, model_used, created_at
                FROM summaries
                WHERE start_date >= ? AND end_date <= ?
                ORDER BY created_at DESC
                """,
                (start_date, end_date),
            )
            rows = cur.fetchall()
            return [
                Summary(
                    id=r[0],
                    start_date=r[1],
                    end_date=r[2],
                    post_count=r[3],
                    summary_text=r[4],
                    model_used=r[5],
                    created_at=r[6],
                )
                for r in rows
            ]

    # Integrity helpers -------------------------------------------------
    def get_total_post_count(self) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM posts")
            return cur.fetchone()[0]

    def get_unique_uri_count(self) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(DISTINCT uri) FROM posts")
            return cur.fetchone()[0]

    def get_duplicate_content_count(self) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT text, COUNT(*) as cnt
                    FROM posts
                    GROUP BY text
                    HAVING cnt > 1
                ) AS duplicates
                """
            )
            return cur.fetchone()[0]

    def get_posts_with_duplicate_content(self) -> List[tuple[str, int]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT text, COUNT(*) as cnt
                FROM posts
                GROUP BY text
                HAVING cnt > 1
                ORDER BY cnt DESC
                """
            )
            return cur.fetchall()

    def find_duplicate_uris(self) -> List[str]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT uri, COUNT(*) as cnt
                FROM posts
                GROUP BY uri
                HAVING cnt > 1
                """
            )
            return [row[0] for row in cur.fetchall()]

    # Pruning / maintenance -------------------------------------------
    def prune_posts_older_than(self, before: dt.datetime) -> int:
        """Delete posts older than the given timestamp.

        Returns number of rows deleted.
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM posts WHERE created_at < ?", (before,))
            deleted = cur.rowcount or 0
            return deleted

    def vacuum(self) -> None:
        with self._connect() as conn:
            conn.execute("VACUUM")

    def get_db_size_bytes(self) -> int:
        try:
            return os.path.getsize(self.db_path)
        except OSError:
            return 0

    # Streaming state -------------------------------------------------
    def get_metadata(self, key: str) -> Optional[str]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT value FROM metadata WHERE key = ?", (key,))
            row = cur.fetchone()
            return row[0] if row else None

    def set_metadata(self, key: str, value: str) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO metadata (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    # Analytics / engagement helpers ----------------------------------
    def get_top_posts(
        self,
        start_date: dt.datetime,
        end_date: dt.datetime,
        limit: int = 10,
        order_by: str = "like_count",
    ) -> List[Post]:
        """Return top engagement posts in a date range.

        order_by can be one of like_count, repost_count, reply_count, total_engagement.
        """
        valid = {"like_count", "repost_count", "reply_count", "total_engagement"}
        if order_by not in valid:
            raise ValueError(f"order_by must be one of {valid}")
        metric_expr = (
            "(like_count + repost_count + reply_count) AS total_engagement"
            if order_by == "total_engagement"
            else order_by
        )
        order_clause = (
            "total_engagement DESC"
            if order_by == "total_engagement"
            else f"{order_by} DESC"
        )
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT id, uri, cid, author_handle, author_did, text, created_at,
                       like_count, repost_count, reply_count, indexed_at, {metric_expr}
                FROM posts
                WHERE created_at BETWEEN ? AND ?
                ORDER BY {order_clause}, created_at DESC
                LIMIT ?
                """,
                (start_date, end_date, limit),
            )
            rows = cur.fetchall()
            return [
                Post(
                    id=r[0],
                    uri=r[1],
                    cid=r[2],
                    author_handle=r[3],
                    author_did=r[4],
                    text=r[5],
                    created_at=r[6],
                    like_count=r[7],
                    repost_count=r[8],
                    reply_count=r[9],
                    indexed_at=r[10],
                )
                for r in rows
            ]
