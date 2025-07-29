"""
Claude AI summarizer for Bluesky feed content.
"""

import logging
from datetime import datetime, timezone
from typing import List
from anthropic import Anthropic
from ..database.models import Post, Summary


logger = logging.getLogger(__name__)


class ClaudeSummarizer:
    """Claude AI-powered text summarizer for Bluesky posts."""

    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        """
        Initialize Claude summarizer.

        Args:
            api_key: Anthropic API key
            model: Claude model to use for summarization
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def summarize_posts(
        self, posts: List[Post], start_date: datetime, end_date: datetime
    ) -> Summary:
        """
        Summarize a list of Bluesky posts using Claude AI.

        Args:
            posts: List of Post objects to summarize
            start_date: Start date of the posts
            end_date: End date of the posts

        Returns:
            Summary object containing the generated summary
        """
        if not posts:
            return Summary(
                id=None,
                start_date=start_date,
                end_date=end_date,
                post_count=0,
                summary_text="No posts found in the specified date range.",
                model_used=self.model,
                created_at=datetime.now(timezone.utc),
            )

        # Prepare posts text for summarization
        posts_text = self._format_posts_for_summarization(posts)

        # Create the prompt
        prompt = self._create_summarization_prompt(
            posts_text, start_date, end_date, len(posts)
        )

        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )

            summary_text = response.content[0].text

            logger.info(f"Generated summary for {len(posts)} posts using {self.model}")

            return Summary(
                id=None,
                start_date=start_date,
                end_date=end_date,
                post_count=len(posts),
                summary_text=summary_text,
                model_used=self.model,
                created_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.error(f"Error generating summary with Claude: {e}")
            raise

    def _format_posts_for_summarization(self, posts: List[Post]) -> str:
        """Format posts into a text block for summarization."""
        formatted_posts = []

        for i, post in enumerate(posts, 1):
            # Format each post with metadata
            post_text = f"""Post {i}:
Author: @{post.author_handle}
Time: {post.created_at.strftime("%Y-%m-%d %H:%M:%S")}
Engagement: {post.like_count} likes, {post.repost_count} reposts, {post.reply_count} replies
Content: {post.text}

---"""
            formatted_posts.append(post_text)

        return "\n".join(formatted_posts)

    def _create_summarization_prompt(
        self, posts_text: str, start_date: datetime, end_date: datetime, post_count: int
    ) -> str:
        """Create a prompt for Claude to summarize the posts."""

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

    def generate_custom_summary(
        self,
        posts: List[Post],
        custom_prompt: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Summary:
        """
        Generate a summary with a custom prompt.

        Args:
            posts: List of Post objects to summarize
            custom_prompt: Custom prompt for summarization
            start_date: Start date of the posts
            end_date: End date of the posts

        Returns:
            Summary object containing the generated summary
        """
        if not posts:
            return Summary(
                id=None,
                start_date=start_date,
                end_date=end_date,
                post_count=0,
                summary_text="No posts found in the specified date range.",
                model_used=self.model,
                created_at=datetime.now(timezone.utc),
            )

        posts_text = self._format_posts_for_summarization(posts)

        full_prompt = f"""{custom_prompt}

Here are the posts to analyze:

{posts_text}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.3,
                messages=[{"role": "user", "content": full_prompt}],
            )

            summary_text = response.content[0].text

            logger.info(
                f"Generated custom summary for {len(posts)} posts using {self.model}"
            )

            return Summary(
                id=None,
                start_date=start_date,
                end_date=end_date,
                post_count=len(posts),
                summary_text=summary_text,
                model_used=f"{self.model} (custom prompt)",
                created_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.error(f"Error generating custom summary with Claude: {e}")
            raise
