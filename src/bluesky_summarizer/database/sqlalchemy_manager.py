"""
SQLAlchemy Core database manager -- dialect-neutral backend.

Supports any database that SQLAlchemy can talk to (SQLite, PostgreSQL,
MySQL, MariaDB, etc.) via a standard connection URL.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Any, List, Optional, Tuple

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Index,
    create_engine,
    func,
    select,
    delete,
    text,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from .base import AbstractDatabaseManager
from .models import Post, Summary


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class SQLAlchemyDatabaseManager(AbstractDatabaseManager):
    """Dialect-neutral database manager built on SQLAlchemy Core."""

    def __init__(self, connection_url: str, **engine_kwargs: Any) -> None:
        self.connection_url = connection_url

        # For SQLite file URLs, make sure parent directory exists
        if connection_url.startswith("sqlite:///") and not connection_url.startswith(
            "sqlite:///:memory:"
        ):
            db_path = connection_url.replace("sqlite:///", "")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        default_kwargs: dict[str, Any] = {"pool_pre_ping": True}
        # SQLite does not support pool_pre_ping with NullPool, but it's fine
        # with the default pool.
        default_kwargs.update(engine_kwargs)
        self.engine: Engine = create_engine(connection_url, **default_kwargs)

        self._metadata = MetaData()
        self._define_tables()
        self._init_schema()

    # ── Table definitions ───────────────────────────────────────────

    def _define_tables(self) -> None:
        self.metadata_table = Table(
            "metadata",
            self._metadata,
            Column("key", String, primary_key=True),
            Column("value", Text, nullable=False),
        )

        self.posts_table = Table(
            "posts",
            self._metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("uri", String, unique=True, nullable=False),
            Column("cid", String, nullable=False),
            Column("author_handle", String, nullable=False),
            Column("author_did", String, nullable=False),
            Column("text", Text, nullable=False),
            Column("created_at", String, nullable=False),
            Column("like_count", Integer, server_default="0"),
            Column("repost_count", Integer, server_default="0"),
            Column("reply_count", Integer, server_default="0"),
            Column("indexed_at", String),
        )

        self.summaries_table = Table(
            "summaries",
            self._metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("start_date", String, nullable=False),
            Column("end_date", String, nullable=False),
            Column("post_count", Integer, nullable=False),
            Column("summary_text", Text, nullable=False),
            Column("model_used", String, nullable=False),
            Column("created_at", String),
        )

        # Indexes
        Index("idx_posts_created_at", self.posts_table.c.created_at)
        Index("idx_posts_author_handle", self.posts_table.c.author_handle)
        Index(
            "idx_posts_author_created",
            self.posts_table.c.author_handle,
            self.posts_table.c.created_at,
        )
        Index(
            "idx_summaries_date_range",
            self.summaries_table.c.start_date,
            self.summaries_table.c.end_date,
        )

    def _init_schema(self) -> None:
        """Create tables and indexes if they don't exist, seed metadata."""
        self._metadata.create_all(self.engine)

        with self.engine.begin() as conn:
            # Seed default metadata rows if missing
            for key, value in [
                ("schema_version", "1"),
                ("last_stream_cursor", ""),
                ("last_stream_time", ""),
            ]:
                existing = conn.execute(
                    select(self.metadata_table.c.value).where(
                        self.metadata_table.c.key == key
                    )
                ).fetchone()
                if existing is None:
                    conn.execute(
                        self.metadata_table.insert().values(key=key, value=value)
                    )

    # ── Helpers ──────────────────────────────────────────────────────

    @property
    def _dialect_name(self) -> str:
        return self.engine.dialect.name

    @staticmethod
    def _row_to_post(row: Any) -> Post:
        """Map a result row (dict-like) to a Post model."""
        created_at = row.created_at
        if isinstance(created_at, str):
            created_at = dt.datetime.fromisoformat(created_at)

        return Post(
            uri=row.uri,
            cid=row.cid,
            author_handle=row.author_handle,
            author_did=row.author_did,
            text=row.text,
            created_at=created_at,
            like_count=row.like_count or 0,
            repost_count=row.repost_count or 0,
            reply_count=row.reply_count or 0,
        )

    @staticmethod
    def _row_to_summary(row: Any) -> Summary:
        """Map a result row to a Summary model."""
        start_date = row.start_date
        if isinstance(start_date, str):
            start_date = dt.datetime.fromisoformat(start_date)
        end_date = row.end_date
        if isinstance(end_date, str):
            end_date = dt.datetime.fromisoformat(end_date)
        created_at = row.created_at
        if isinstance(created_at, str):
            created_at = dt.datetime.fromisoformat(created_at)

        return Summary(
            start_date=start_date,
            end_date=end_date,
            post_count=row.post_count,
            summary_text=row.summary_text,
            model_used=row.model_used,
            created_at=created_at,
        )

    def _upsert_post_values(self, post: Post) -> dict:
        return {
            "uri": post.uri,
            "cid": post.cid,
            "author_handle": post.author_handle,
            "author_did": post.author_did,
            "text": post.text,
            "created_at": post.created_at.isoformat(),
            "like_count": post.like_count,
            "repost_count": post.repost_count,
            "reply_count": post.reply_count,
            "indexed_at": _utcnow().isoformat(),
        }

    def _build_upsert(self, values: dict) -> Any:
        """Build a dialect-appropriate upsert statement."""
        update_cols = {
            "cid": values["cid"],
            "author_handle": values["author_handle"],
            "author_did": values["author_did"],
            "text": values["text"],
            "created_at": values["created_at"],
            "like_count": values["like_count"],
            "repost_count": values["repost_count"],
            "reply_count": values["reply_count"],
            "indexed_at": values["indexed_at"],
        }

        if self._dialect_name == "postgresql":
            stmt = pg_insert(self.posts_table).values(**values)
            return stmt.on_conflict_do_update(
                index_elements=["uri"], set_=update_cols
            )
        else:
            # SQLite (and compatible) dialect
            stmt = sqlite_insert(self.posts_table).values(**values)
            return stmt.on_conflict_do_update(
                index_elements=["uri"], set_=update_cols
            )

    # ── Post operations ─────────────────────────────────────────────

    def save_post(self, post: Post) -> int:
        values = self._upsert_post_values(post)
        stmt = self._build_upsert(values)
        with self.engine.begin() as conn:
            result = conn.execute(stmt)
            return result.inserted_primary_key[0] if result.inserted_primary_key else 0

    def save_posts(self, posts: List[Post]) -> dict:
        if not posts:
            return {"new": 0, "updated": 0, "total": 0}

        with self.engine.begin() as conn:
            # Determine which URIs already exist in the database
            uris = [p.uri for p in posts]
            existing_uris: set[str] = set()
            chunk_size = 900
            for i in range(0, len(uris), chunk_size):
                chunk = uris[i : i + chunk_size]
                rows = conn.execute(
                    select(self.posts_table.c.uri).where(
                        self.posts_table.c.uri.in_(chunk)
                    )
                ).fetchall()
                existing_uris.update(r[0] for r in rows)

            # Track URIs seen within this batch to detect intra-batch duplicates
            new_count = 0
            updated_count = 0
            seen_uris: set[str] = set()

            for post in posts:
                if post.uri in existing_uris or post.uri in seen_uris:
                    updated_count += 1
                else:
                    new_count += 1
                seen_uris.add(post.uri)

                values = self._upsert_post_values(post)
                stmt = self._build_upsert(values)
                conn.execute(stmt)

            return {"new": new_count, "updated": updated_count, "total": len(posts)}

    def get_posts_by_date_range(
        self, start_date: dt.datetime, end_date: dt.datetime
    ) -> List[Post]:
        stmt = (
            select(
                self.posts_table.c.uri,
                self.posts_table.c.cid,
                self.posts_table.c.author_handle,
                self.posts_table.c.author_did,
                self.posts_table.c.text,
                self.posts_table.c.created_at,
                self.posts_table.c.like_count,
                self.posts_table.c.repost_count,
                self.posts_table.c.reply_count,
            )
            .where(self.posts_table.c.created_at >= start_date.isoformat())
            .where(self.posts_table.c.created_at <= end_date.isoformat())
            .order_by(self.posts_table.c.created_at.asc())
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
            return [self._row_to_post(row) for row in rows]

    def get_posts_by_author(
        self,
        author_handle: str,
        start_date: Optional[dt.datetime] = None,
        end_date: Optional[dt.datetime] = None,
    ) -> List[Post]:
        stmt = select(
            self.posts_table.c.uri,
            self.posts_table.c.cid,
            self.posts_table.c.author_handle,
            self.posts_table.c.author_did,
            self.posts_table.c.text,
            self.posts_table.c.created_at,
            self.posts_table.c.like_count,
            self.posts_table.c.repost_count,
            self.posts_table.c.reply_count,
        ).where(self.posts_table.c.author_handle == author_handle)

        if start_date and end_date:
            stmt = stmt.where(
                self.posts_table.c.created_at >= start_date.isoformat()
            ).where(self.posts_table.c.created_at <= end_date.isoformat())

        stmt = stmt.order_by(self.posts_table.c.created_at.asc())
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
            return [self._row_to_post(row) for row in rows]

    def get_post_count(
        self,
        start_date: Optional[dt.datetime] = None,
        end_date: Optional[dt.datetime] = None,
    ) -> int:
        stmt = select(func.count()).select_from(self.posts_table)
        if start_date and end_date:
            stmt = stmt.where(
                self.posts_table.c.created_at >= start_date.isoformat()
            ).where(self.posts_table.c.created_at <= end_date.isoformat())

        with self.engine.connect() as conn:
            return conn.execute(stmt).scalar() or 0

    def get_total_post_count(self) -> int:
        return self.get_post_count()

    def get_unique_uri_count(self) -> int:
        stmt = select(func.count(func.distinct(self.posts_table.c.uri)))
        with self.engine.connect() as conn:
            return conn.execute(stmt).scalar() or 0

    def find_duplicate_uris(self) -> List[str]:
        stmt = (
            select(self.posts_table.c.uri)
            .group_by(self.posts_table.c.uri)
            .having(func.count() > 1)
        )
        with self.engine.connect() as conn:
            return [row[0] for row in conn.execute(stmt).fetchall()]

    def get_posts_with_duplicate_content(self) -> List[Tuple[str, int]]:
        cnt = func.count().label("cnt")
        stmt = (
            select(self.posts_table.c.text, cnt)
            .group_by(self.posts_table.c.text)
            .having(cnt > 1)
        )
        with self.engine.connect() as conn:
            return [(row[0], row[1]) for row in conn.execute(stmt).fetchall()]

    def get_duplicate_content_count(self) -> int:
        cnt = func.count().label("cnt")
        sub = (
            select(self.posts_table.c.text, cnt)
            .group_by(self.posts_table.c.text)
            .having(cnt > 1)
        ).subquery()
        stmt = select(func.count()).select_from(sub)
        with self.engine.connect() as conn:
            return conn.execute(stmt).scalar() or 0

    def delete_old_posts(self, cutoff_date: dt.datetime) -> int:
        stmt = delete(self.posts_table).where(
            self.posts_table.c.created_at < cutoff_date.isoformat()
        )
        with self.engine.begin() as conn:
            result = conn.execute(stmt)
            return result.rowcount

    def prune_posts_older_than(self, before: dt.datetime) -> int:
        return self.delete_old_posts(before)

    # ── Summary operations ──────────────────────────────────────────

    def save_summary(self, summary: Summary) -> int:
        values = {
            "start_date": summary.start_date.isoformat(),
            "end_date": summary.end_date.isoformat(),
            "post_count": summary.post_count,
            "summary_text": summary.summary_text,
            "model_used": summary.model_used,
            "created_at": _utcnow().isoformat(),
        }
        with self.engine.begin() as conn:
            result = conn.execute(self.summaries_table.insert().values(**values))
            return result.inserted_primary_key[0] if result.inserted_primary_key else 0

    def get_summary_by_date_range(
        self, start_date: dt.datetime, end_date: dt.datetime
    ) -> Optional[Summary]:
        stmt = (
            select(
                self.summaries_table.c.start_date,
                self.summaries_table.c.end_date,
                self.summaries_table.c.post_count,
                self.summaries_table.c.summary_text,
                self.summaries_table.c.model_used,
                self.summaries_table.c.created_at,
            )
            .where(self.summaries_table.c.start_date <= start_date.isoformat())
            .where(self.summaries_table.c.end_date >= end_date.isoformat())
            .order_by(self.summaries_table.c.created_at.desc())
            .limit(1)
        )
        with self.engine.connect() as conn:
            row = conn.execute(stmt).fetchone()
            return self._row_to_summary(row) if row else None

    def get_recent_summaries(self, limit: int = 10) -> List[Summary]:
        stmt = (
            select(
                self.summaries_table.c.start_date,
                self.summaries_table.c.end_date,
                self.summaries_table.c.post_count,
                self.summaries_table.c.summary_text,
                self.summaries_table.c.model_used,
                self.summaries_table.c.created_at,
            )
            .order_by(self.summaries_table.c.created_at.desc())
            .limit(limit)
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
            return [self._row_to_summary(row) for row in rows]

    def get_latest_summary(self) -> Optional[Summary]:
        summaries = self.get_recent_summaries(limit=1)
        return summaries[0] if summaries else None

    # ── Metadata operations ─────────────────────────────────────────

    def set_metadata(self, key: str, value: str) -> None:
        with self.engine.begin() as conn:
            # Try update first, then insert if no rows affected
            result = conn.execute(
                self.metadata_table.update()
                .where(self.metadata_table.c.key == key)
                .values(value=value)
            )
            if result.rowcount == 0:
                conn.execute(
                    self.metadata_table.insert().values(key=key, value=value)
                )

    def get_metadata(self, key: str) -> Optional[str]:
        stmt = select(self.metadata_table.c.value).where(
            self.metadata_table.c.key == key
        )
        with self.engine.connect() as conn:
            row = conn.execute(stmt).fetchone()
            return row[0] if row else None

    # ── Maintenance operations ──────────────────────────────────────

    def vacuum(self) -> None:
        """Reclaim space. Only meaningful for SQLite; no-op for others."""
        if self._dialect_name == "sqlite":
            # VACUUM cannot run inside a transaction in SQLite
            raw_conn = self.engine.raw_connection()
            try:
                raw_conn.execute("VACUUM")
            finally:
                raw_conn.close()

    def get_db_size_bytes(self) -> int:
        """Return approximate database file size in bytes."""
        if self._dialect_name == "sqlite":
            # Extract file path from URL
            url_str = str(self.engine.url)
            db_path = url_str.replace("sqlite:///", "")
            if db_path and os.path.exists(db_path):
                return os.path.getsize(db_path)
            return 0

        # For server-based databases, query pg_database_size or similar
        if self._dialect_name == "postgresql":
            with self.engine.connect() as conn:
                row = conn.execute(
                    text("SELECT pg_database_size(current_database())")
                ).fetchone()
                return row[0] if row else 0

        return 0

    def close(self) -> None:
        """Dispose of the engine and all connections."""
        self.engine.dispose()


__all__ = ["SQLAlchemyDatabaseManager"]
