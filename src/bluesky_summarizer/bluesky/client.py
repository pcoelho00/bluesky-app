"""
Bluesky API client for fetching timeline posts.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from atproto import Client, models
from ..database.models import Post


logger = logging.getLogger(__name__)


class BlueSkyClient:
    """Client for interacting with Bluesky's AT Protocol API."""

    def __init__(self, handle: str, password: str):
        """Initialize the Bluesky client with user credentials."""
        self.handle = handle
        self.password = password
        self.client = Client()
        self._authenticated = False

    def authenticate(self) -> bool:
        """Authenticate with Bluesky API."""
        try:
            self.client.login(self.handle, self.password)
            self._authenticated = True
            logger.info(f"Successfully authenticated as {self.handle}")
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            self._authenticated = False
            return False

    def fetch_timeline_posts(
        self, start_date: datetime, end_date: datetime, limit: int = 100
    ) -> List[Post]:
        """
        Fetch timeline posts within a specific date range.

        Args:
            start_date: Start of the date range
            end_date: End of the date range
            limit: Maximum number of posts to fetch per request

        Returns:
            List of Post objects
        """
        if not self._authenticated:
            if not self.authenticate():
                raise RuntimeError("Failed to authenticate with Bluesky API")

        # Ensure start_date and end_date are timezone-aware (UTC)
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        posts = []
        cursor = None

        try:
            while True:
                # Fetch timeline
                response = self.client.get_timeline(
                    algorithm="reverse-chronological",
                    limit=min(limit, 100),  # API limit is typically 100
                    cursor=cursor,
                )

                if not response.feed:
                    break

                batch_posts = []
                oldest_post_date = None

                for feed_item in response.feed:
                    post = feed_item.post

                    # Parse the post creation date
                    created_at = datetime.fromisoformat(
                        post.record.created_at.replace("Z", "+00:00")
                    )

                    # Check if post is within our date range
                    if created_at < start_date:
                        # We've gone past our start date, stop fetching
                        oldest_post_date = created_at
                        break

                    if created_at <= end_date:
                        # Convert to our Post model
                        post_obj = self._convert_to_post_model(post, created_at)
                        batch_posts.append(post_obj)

                    oldest_post_date = created_at

                posts.extend(batch_posts)

                # Stop if we've reached the start date or no more posts
                if oldest_post_date and oldest_post_date < start_date:
                    break

                if not response.cursor:
                    break

                cursor = response.cursor

                # Safety limit to avoid infinite loops
                if len(posts) >= limit * 10:
                    logger.warning(f"Reached safety limit of {limit * 10} posts")
                    break

        except Exception as e:
            logger.error(f"Error fetching timeline posts: {e}")
            raise

        # Filter posts to exact date range and sort
        filtered_posts = [
            post for post in posts if start_date <= post.created_at <= end_date
        ]

        filtered_posts.sort(key=lambda p: p.created_at)

        logger.info(
            f"Fetched {len(filtered_posts)} posts from {start_date} to {end_date}"
        )
        return filtered_posts

    def _convert_to_post_model(
        self,
        atproto_post: models.AppBskyFeedDefs.PostView,
        created_at: datetime,
    ) -> Post:
        """Convert AT Protocol post to our Post model."""

        # Get engagement metrics
        like_count = atproto_post.like_count or 0
        repost_count = atproto_post.repost_count or 0
        reply_count = atproto_post.reply_count or 0

        # Get author information
        author = atproto_post.author
        author_handle = author.handle
        author_did = author.did

        # Get post content
        text = atproto_post.record.text if hasattr(atproto_post.record, "text") else ""

        return Post(
            id=None,  # Will be set by database
            uri=atproto_post.uri,
            cid=atproto_post.cid,
            author_handle=author_handle,
            author_did=author_did,
            text=text,
            created_at=created_at,
            like_count=like_count,
            repost_count=repost_count,
            reply_count=reply_count,
            indexed_at=datetime.now(timezone.utc),
        )

    def get_user_profile(self, handle: Optional[str] = None) -> Optional[dict]:
        """Get user profile information."""
        if not self._authenticated:
            if not self.authenticate():
                return None

        try:
            profile = self.client.get_profile(handle or self.handle)
            return {
                "handle": profile.handle,
                "display_name": profile.display_name,
                "description": profile.description,
                "followers_count": profile.followers_count,
                "follows_count": profile.follows_count,
                "posts_count": profile.posts_count,
            }
        except Exception as e:
            logger.error(f"Error fetching profile: {e}")
            return None
