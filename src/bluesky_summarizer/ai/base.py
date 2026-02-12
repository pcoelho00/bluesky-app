"""Shared utilities for AI summarizers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from ..database.models import Post, Summary

try:
    from ..config import config  # type: ignore
except Exception:  # pragma: no cover
    config = None  # type: ignore


DEFAULT_MAX_OUTPUT_TOKENS = 4096


class _BaseSummarizer:
    model: str

    def _empty_summary(self, start_date: datetime, end_date: datetime) -> Summary:
        return Summary(
            id=None,
            start_date=start_date,
            end_date=end_date,
            post_count=0,
            summary_text="No posts found in the specified date range.",
            model_used=self.model,
            created_at=datetime.now(timezone.utc),
        )

    def _summary_from_text(
        self,
        summary_text: str,
        start_date: datetime,
        end_date: datetime,
        post_count: int,
        model_used: str | None = None,
    ) -> Summary:
        return Summary(
            id=None,
            start_date=start_date,
            end_date=end_date,
            post_count=post_count,
            summary_text=summary_text,
            model_used=model_used or self.model,
            created_at=datetime.now(timezone.utc),
        )

    def _get_max_prompt_chars(self) -> int:
        max_chars = 20000
        try:
            if config and getattr(config, "app", None):
                max_chars = config.app.max_prompt_chars
        except Exception:
            pass
        return max_chars

    def _format_posts_for_summarization(self, posts: List[Post]) -> str:
        """Format posts into a text block for summarization."""
        formatted_posts = []

        for i, post in enumerate(posts, 1):
            post_text = f"""Post {i}:
Author: @{post.author_handle}
Time: {post.created_at.strftime("%Y-%m-%d %H:%M:%S")}
Engagement: {post.like_count} likes, {post.repost_count} reposts, {post.reply_count} replies
Content: {post.text}

---"""
            formatted_posts.append(post_text)

        return "\n".join(formatted_posts)

    def _truncate_posts(self, posts: List[Post], max_chars: int) -> List[Post]:
        """Truncate posts list to fit within character budget when formatted.

        Strategy:
          1. Sort by engagement (likes + reposts + replies) descending, then recency.
          2. Keep adding formatted length until budget would be exceeded.
          3. Fall back to chronological if all have zero engagement.
        """
        if not posts:
            return posts
        scored = []
        for p in posts:
            engagement = p.like_count + p.repost_count + p.reply_count
            scored.append((engagement, p.created_at, p))
        if all(s[0] == 0 for s in scored):
            ordered = [p for _, _, p in sorted(scored, key=lambda x: x[1])]
        else:
            ordered = [
                p
                for _, _, p in sorted(scored, key=lambda x: (-x[0], -x[1].timestamp()))
            ]
        selected: List[Post] = []
        total_chars = 0
        for cand in ordered:
            frag = self._format_posts_for_summarization([cand])
            frag_len = len(frag) + 1
            if total_chars + frag_len > max_chars and selected:
                break
            if frag_len > max_chars and not selected:
                truncated_text = cand.text[: max(0, max_chars - 200)] + "..."
                cand = cand.model_copy(update={"text": truncated_text})
                selected.append(cand)
                break
            selected.append(cand)
            total_chars += frag_len
        return selected

    def _create_summarization_prompt(
        self, posts_text: str, start_date: datetime, end_date: datetime, post_count: int
    ) -> str:
        """Create a prompt to summarize the posts."""

        date_range = (
            f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        )

        prompt = f"""Please analyze and summarize the following {post_count} Bluesky social media posts from {date_range}.

Your summary should include:

1. **Key Themes**: What are the main topics and themes discussed?
2. **Notable Conversations**: Highlight any particularly engaging or important discussions
3. **Trending Topics**: What subjects seem to be getting the most attention?
4. **Sentiment Overview**: What's the general mood or sentiment of the posts?
5. **Interesting Insights**: Any notable patterns, insights, or observations

Please provide a concise but comprehensive summary that captures the essence of the social media activity during this period. Focus on the most important and engaging content.

Here are the posts:

{posts_text}

Please provide your summary in a clear, well-structured format with appropriate headings."""

        return prompt
