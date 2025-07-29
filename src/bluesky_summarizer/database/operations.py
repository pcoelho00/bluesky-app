"""
Database operations for managing Bluesky posts and summaries.
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Optional
from .models import Post, Summary


class DatabaseManager:
    """Manages SQLite database operations for Bluesky posts and summaries."""

    def __init__(self, db_path: str):
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

    def save_posts(self, posts: List[Post]) -> int:
        """Save multiple posts to the database. Returns the number of posts saved."""
        count = 0
        for post in posts:
            try:
                self.save_post(post)
                count += 1
            except sqlite3.IntegrityError:
                # Post already exists, skip
                continue
        return count

    def get_posts_by_date_range(
        self, start_date: datetime, end_date: datetime
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

    def get_summaries_by_date_range(
        self, start_date: datetime, end_date: datetime
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
        self, start_date: datetime, end_date: datetime
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
