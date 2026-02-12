"""Gemini AI summarizer for Bluesky feed content."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from google import genai
from google.genai import types

from .base import _BaseSummarizer, DEFAULT_MAX_OUTPUT_TOKENS
from ..database.models import Post, Summary

logger = logging.getLogger(__name__)


class GeminiSummarizer(_BaseSummarizer):
    """Gemini AI-powered text summarizer for Bluesky posts."""

    def __init__(self, api_key: str, model: str = "gemini-3-flash-preview"):
        """Initialize Gemini summarizer."""
        self.model = model
        self.client = genai.Client(api_key=api_key)

    def _generate_content(self, prompt: str) -> str:
        """Generate content using the Gemini models API."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            ),
        )
        summary_text = getattr(response, "text", "") or ""
        summary_text = summary_text.strip()
        if not summary_text:
            return "Summary generation returned empty response."

        return summary_text

    def summarize_posts(
        self, posts: List[Post], start_date: datetime, end_date: datetime
    ) -> Summary:
        """Summarize a list of Bluesky posts using Gemini."""
        if not posts:
            return self._empty_summary(start_date, end_date)

        max_chars = self._get_max_prompt_chars()
        truncated_posts = self._truncate_posts(posts, max_chars)
        posts_text = self._format_posts_for_summarization(truncated_posts)
        prompt = self._create_summarization_prompt(
            posts_text, start_date, end_date, len(truncated_posts)
        )

        try:
            summary_text = self._generate_content(prompt)

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
            logger.error(f"Error generating summary with Gemini: {e}")
            raise
