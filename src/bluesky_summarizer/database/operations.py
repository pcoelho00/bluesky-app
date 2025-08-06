"""
Database operations for managing Bluesky posts and summaries.
"""

import sqlite3
import os
import datetime as dt
from typing import Any, List, Optional
from .models import Post, Summary


# https://docs.python.org/3/library/sqlite3.html#sqlite3-adapter-converter-recipes
def adapt_date_iso(val: Any) -> Any:
    """Adapt datetime.date to ISO 8601 date."""
    return val.isoformat()


def adapt_datetime_iso(val: Any) -> Any:
    """Adapt datetime.datetime to timezone-naive ISO 8601 date."""
    return val.replace(tzinfo=None).isoformat()


def adapt_datetime_epoch(val: Any) -> int:
    """Adapt datetime.datetime to Unix timestamp."""
    return int(val.timestamp())


sqlite3.register_adapter(dt.date, adapt_date_iso)
sqlite3.register_adapter(dt.datetime, adapt_datetime_iso)
sqlite3.register_adapter(dt.datetime, adapt_datetime_epoch)


def convert_date(val: Any) -> dt.date:
    """Convert ISO 8601 date to datetime.date object."""
    return dt.date.fromisoformat(val.decode())


def convert_datetime(val: Any) -> dt.datetime:
    """Convert ISO 8601 datetime to datetime.datetime object."""
    return dt.datetime.fromisoformat(val.decode())


def convert_timestamp(val: Any) -> dt.datetime:
    """Convert Unix epoch timestamp to datetime.datetime object."""
    return dt.datetime.fromtimestamp(int(val))


sqlite3.register_converter("date", convert_date)
sqlite3.register_converter("datetime", convert_datetime)
sqlite3.register_converter("timestamp", convert_timestamp)


class DatabaseManager:
    """Manages SQLite database operations for Bluesky posts and summaries."""

    def __init__(self, db_path: str) -> None:
        """Initialize database manager with database path."""
        self.db_path = db_path
        self._ensure_database_directory()
        self._initialize_database()

    def _ensure_database_directory(self) -> None:
        """Create database directory if it doesn't exist."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def _initialize_database(self) -> None:
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create posts table
            cursor.execute("""
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
            """)

            # Create summaries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_date TIMESTAMP NOT NULL,
                    end_date TIMESTAMP NOT NULL,
                    post_count INTEGER NOT NULL,
                    summary_text TEXT NOT NULL,
                    model_used TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for better performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_author_handle ON posts(author_handle)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_summaries_date_range ON summaries(start_date, end_date)"
            )

            conn.commit()

    def save_post(self, post: Post) -> int:
        """Save a post to the database. Returns the post ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
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

            return cursor.lastrowid

    def post_exists(self, uri: str) -> bool:
        """Check if a post with the given URI already exists in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM posts WHERE uri = ? LIMIT 1", (uri,))
            return cursor.fetchone() is not None

    def get_existing_uris(self, uris: List[str]) -> set[str]:
        """Get a set of URIs that already exist in the database."""
        if not uris:
            return set()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(uris))
            cursor.execute(f"SELECT uri FROM posts WHERE uri IN ({placeholders})", uris)
            return {row[0] for row in cursor.fetchall()}

    def save_posts(self, posts: List[Post]) -> dict[str, int]:
        """
        Save multiple posts to the database.
        Returns a dictionary with counts: {'new': int, 'updated': int, 'total': int}
        """
        if not posts:
            return {"new": 0, "updated": 0, "total": 0}

        # Get existing URIs to determine which posts are new vs updates
        post_uris = [post.uri for post in posts]
        existing_uris = self.get_existing_uris(post_uris)

        new_count = 0
        updated_count = 0
        processed_in_batch = set()  # Track URIs we've seen in this batch

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            for post in posts:
                try:
                    # Check if this URI was already in DB or processed in this batch
                    is_existing = (
                        post.uri in existing_uris or post.uri in processed_in_batch
                    )

                    cursor.execute(
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

                    if is_existing:
                        updated_count += 1
                    else:
                        new_count += 1

                    # Mark this URI as processed in this batch
                    processed_in_batch.add(post.uri)

                except sqlite3.Error as e:
                    # Log the error but continue with other posts
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"Error saving post {post.uri}: {e}")
                    continue

            conn.commit()

        return {
            "new": new_count,
            "updated": updated_count,
            "total": new_count + updated_count,
        }

    def get_posts_by_date_range(
        self, start_date: dt.datetime, end_date: dt.datetime
    ) -> List[Post]:
        """Get posts within a specific date range."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, uri, cid, author_handle, author_did, text, created_at,
                       like_count, repost_count, reply_count, indexed_at
                FROM posts
                WHERE created_at BETWEEN ? AND ?
                ORDER BY created_at ASC
            """,
                (start_date, end_date),
            )

            rows = cursor.fetchall()
            return [
                Post(
                    id=row[0],
                    uri=row[1],
                    cid=row[2],
                    author_handle=row[3],
                    author_did=row[4],
                    text=row[5],
                    created_at=row[6],
                    like_count=row[7],
                    repost_count=row[8],
                    reply_count=row[9],
                    indexed_at=row[10],
                )
                for row in rows
            ]

    def save_summary(self, summary: Summary) -> int:
        """Save a summary to the database. Returns the summary ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
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

            return cursor.lastrowid

    def get_latest_summary(self) -> Optional[Summary]:
        """Get the most recent summary from the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, start_date, end_date, post_count, summary_text, model_used, created_at
                FROM summaries
                ORDER BY created_at DESC
                LIMIT 1
            """)

            row = cursor.fetchone()
            if row:
                return Summary(
                    id=row[0],
                    start_date=row[1],
                    end_date=row[2],
                    post_count=row[3],
                    summary_text=row[4],
                    model_used=row[5],
                    created_at=row[6],
                )
            return None

    def get_total_post_count(self) -> int:
        """Get the total number of posts in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM posts")
            return cursor.fetchone()[0]

    def get_unique_uri_count(self) -> int:
        """Get the number of unique URIs in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT uri) FROM posts")
            return cursor.fetchone()[0]

    def get_duplicate_content_count(self) -> int:
        """Get the number of posts that have duplicate text content."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM (
                    SELECT text, COUNT(*) as cnt 
                    FROM posts 
                    GROUP BY text 
                    HAVING cnt > 1
                ) AS duplicates
            """)
            return cursor.fetchone()[0]

    def get_posts_with_duplicate_content(self) -> List[tuple[str, int]]:
        """Get posts that have duplicate text content. Returns (text, count) tuples."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT text, COUNT(*) as cnt 
                FROM posts 
                GROUP BY text 
                HAVING cnt > 1
                ORDER BY cnt DESC
            """)
            return cursor.fetchall()

    def find_duplicate_uris(self) -> List[str]:
        """Find any duplicate URIs in the database (should be none due to UNIQUE constraint)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT uri, COUNT(*) as cnt 
                FROM posts 
                GROUP BY uri 
                HAVING cnt > 1
            """)
            return [row[0] for row in cursor.fetchall()]

    def get_summaries_by_date_range(
        self, start_date: dt.datetime, end_date: dt.datetime
    ) -> List[Summary]:
        """Get summaries within a specific date range."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, start_date, end_date, post_count, summary_text, model_used, created_at
                FROM summaries
                WHERE start_date >= ? AND end_date <= ?
                ORDER BY created_at DESC
            """,
                (start_date, end_date),
            )

            rows = cursor.fetchall()
            return [
                Summary(
                    id=row[0],
                    start_date=row[1],
                    end_date=row[2],
                    post_count=row[3],
                    summary_text=row[4],
                    model_used=row[5],
                    created_at=row[6],
                )
                for row in rows
            ]

    def get_post_count_by_date_range(
        self, start_date: dt.datetime, end_date: dt.datetime
    ) -> int:
        """Get the count of posts within a specific date range."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM posts
                WHERE created_at BETWEEN ? AND ?
            """,
                (start_date, end_date),
            )

            return cursor.fetchone()[0]
