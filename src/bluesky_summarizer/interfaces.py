"""Service layer interface (protocol) definitions for improved testability."""

from __future__ import annotations

from typing import Protocol, List, Iterable
from datetime import datetime

from .database.models import Post, Summary


class IPostRepository(Protocol):
    def save_posts(self, posts: List[Post]) -> dict[str, int]: ...  # noqa: D401
    def get_posts_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> List[Post]: ...  # noqa: D401,E501
    def get_top_posts(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 10,
        order_by: str = "like_count",
    ) -> List[Post]: ...  # noqa: D401,E501


class IPostSource(Protocol):
    def fetch_timeline_posts(
        self, start_date: datetime, end_date: datetime, limit: int = 100
    ) -> List[Post]: ...  # noqa: D401,E501


class ISummarizer(Protocol):
    def summarize_posts(
        self, posts: List[Post], start_date: datetime, end_date: datetime
    ) -> Summary: ...  # noqa: D401,E501
    def generate_custom_summary(
        self,
        posts: List[Post],
        custom_prompt: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Summary: ...  # noqa: D401,E501


class IPrunableRepository(Protocol):
    def prune_posts_older_than(
        self, before: datetime
    ) -> int: ...  # returns rows deleted
    def stream_posts(self) -> Iterable[Post]: ...
