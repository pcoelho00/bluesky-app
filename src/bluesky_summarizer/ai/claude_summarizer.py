"""Claude AI summarizer for Bluesky feed content."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from anthropic import Anthropic

from .base import _BaseSummarizer, DEFAULT_MAX_OUTPUT_TOKENS
from ..database.models import Post, Summary

logger = logging.getLogger(__name__)


class ClaudeSummarizer(_BaseSummarizer):
    """Claude AI-powered text summarizer for Bluesky posts."""

    def __init__(self, api_key: str, model: str = "claude-3-7-sonnet-latest"):
        """Initialize Claude summarizer."""
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def summarize_posts(
        self, posts: List[Post], start_date: datetime, end_date: datetime
    ) -> Summary:
        """Summarize a list of Bluesky posts using Claude AI."""
        if not posts:
            return self._empty_summary(start_date, end_date)

        max_chars = self._get_max_prompt_chars()
        truncated_posts = self._truncate_posts(posts, max_chars)
        posts_text = self._format_posts_for_summarization(truncated_posts)

        prompt = self._create_summarization_prompt(
            posts_text, start_date, end_date, len(truncated_posts)
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )

            summary_text = response.content[0].text

            logger.info(
                "Generated summary for %s posts (original %s) using %s",
                len(truncated_posts),
                len(posts),
                self.model,
            )

            return self._summary_from_text(
                summary_text,
                start_date,
                end_date,
                len(truncated_posts),
            )

        except Exception as e:
            logger.error(f"Error generating summary with Claude: {e}")
            raise

    def generate_custom_summary(
        self,
        posts: List[Post],
        custom_prompt: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Summary:
        """Generate a summary with a custom prompt."""
        if not posts:
            return self._empty_summary(start_date, end_date)

        posts_text = self._format_posts_for_summarization(posts)

        full_prompt = f"""{custom_prompt}

Here are the posts to analyze:

{posts_text}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                temperature=0.3,
                messages=[{"role": "user", "content": full_prompt}],
            )

            summary_text = response.content[0].text

            logger.info(
                "Generated custom summary for %s posts using %s",
                len(posts),
                self.model,
            )

            return self._summary_from_text(
                summary_text,
                start_date,
                end_date,
                len(posts),
                model_used=f"{self.model} (custom prompt)",
            )

        except Exception as e:
            logger.error(f"Error generating custom summary with Claude: {e}")
            raise
