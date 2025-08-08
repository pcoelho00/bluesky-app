"""
Real-time streaming service for Bluesky feeds.

This module provides a service that continuously monitors Bluesky for new posts
and updates the database in real-time using periodic polling.
"""

import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Set, Dict, Any
from threading import Lock
import time

from atproto import Client

from ..database import DatabaseManager
from ..database.models import Post
from ..config import config


logger = logging.getLogger(__name__)


class StreamingService:
    """
    Real-time streaming service for monitoring Bluesky posts.

    Uses periodic polling to check for new posts and stores them in the database.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        user_handles: Optional[Set[str]] = None,
        keywords: Optional[Set[str]] = None,
        poll_interval: int = 30,
        bluesky_handle: Optional[str] = None,
        bluesky_password: Optional[str] = None,
    ):
        """Initialize the streaming service and its internal state."""
        # Core config
        self.db_manager = db_manager or DatabaseManager(config.database.path)
        self.user_handles = user_handles or set()
        self.keywords = keywords or set()
        self.poll_interval = poll_interval

        # Authentication
        self.bluesky_handle = bluesky_handle or config.bluesky.handle
        self.bluesky_password = bluesky_password or config.bluesky.password
        self.client = Client()
        self._authenticated = False

        # State management
        self.is_running = False
        self.posts_processed = 0
        self.posts_saved = 0
        self.start_time = None
        self.last_check = None
        self._stats_lock = Lock()
        self._stop_event = threading.Event()

        # Thread / worker state
        self._worker_thread = None

        # Error/backoff state
        self._consecutive_errors = 0
        self._max_backoff = 300  # seconds
        self._base_backoff = 2

        # Streaming continuity state (persisted in metadata)
        self._last_cursor = None
        self._last_stream_time = None

    # Removed in-library signal handling; caller manages signals.

    def _authenticate(self) -> bool:
        """Authenticate with Bluesky API."""
        try:
            success = self.client.login(self.bluesky_handle, self.bluesky_password)
            if success:
                self._authenticated = True
                logger.info(f"Successfully authenticated as {self.bluesky_handle}")
                return True
            else:
                logger.error("Authentication failed: login returned False")
                self._authenticated = False
                return False
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            self._authenticated = False
            return False

    def _should_process_post(self, author_handle: str, text: str) -> bool:
        """
        Determine if a post should be processed based on filters.

        Args:
            author_handle: Author's handle
            text: Post text content

        Returns:
            True if post should be processed, False otherwise
        """
        # If we have specific users to follow, check if author is in the list
        if self.user_handles and author_handle not in self.user_handles:
            return False

        # If we have keywords to filter by, check if any are in the text
        if self.keywords:
            text_lower = text.lower()
            if not any(keyword.lower() in text_lower for keyword in self.keywords):
                return False

        return True

    def _fetch_recent_posts(self) -> list[Post]:
        """
        Fetch recent posts from Bluesky timeline.

        Returns:
            List of Post objects
        """
        if not self._authenticated:
            if not self._authenticate():
                return []

        try:
            # Determine window using last_stream_time if available
            end_time = datetime.now(timezone.utc)

            # Use a more lenient time window for continuous streaming
            if self._last_stream_time:
                # Use a longer lookback window to ensure we don't miss posts
                # Look back at least poll_interval * 3 or 5 minutes, whichever is longer
                lookback_seconds = max(
                    self.poll_interval * 3, 300
                )  # At least 5 minutes
                start_time = end_time - timedelta(seconds=lookback_seconds)
            else:
                # Initial fetch: look back poll_interval * 2
                start_time = end_time - timedelta(seconds=self.poll_interval * 2)

            # Fetch timeline posts
            # For streaming, we want the latest posts each time, not pagination
            # So we don't use cursor for continuous fetching
            response = self.client.get_timeline(
                algorithm="reverse-chronological",
                limit=50,
                cursor=None,  # Always get latest posts for streaming
            )

            posts = []
            for feed_item in response.feed:
                post = feed_item.post

                # Parse the post creation date
                created_at = datetime.fromisoformat(
                    post.record.created_at.replace("Z", "+00:00")
                )

                # Only process posts within our time window
                if created_at < start_time:
                    continue

                # Get author information
                author = post.author
                author_handle = author.handle
                author_did = author.did

                # Get post content
                text = post.record.text if hasattr(post.record, "text") else ""

                with self._stats_lock:
                    self.posts_processed += 1

                # Apply filters
                if not self._should_process_post(author_handle, text):
                    continue

                # Get engagement metrics
                like_count = post.like_count or 0
                repost_count = post.repost_count or 0
                reply_count = post.reply_count or 0

                # Create Post object
                post_obj = Post(
                    id=None,
                    uri=post.uri,
                    cid=post.cid,
                    author_handle=author_handle,
                    author_did=author_did,
                    text=text,
                    created_at=created_at,
                    like_count=like_count,
                    repost_count=repost_count,
                    reply_count=reply_count,
                    indexed_at=datetime.now(timezone.utc),
                )

                posts.append(post_obj)
                # Track most recent seen time
                if (not self._last_stream_time) or created_at > self._last_stream_time:
                    self._last_stream_time = created_at

            return posts

        except Exception as e:
            logger.error(f"Error fetching recent posts: {e}")
            return []

    def _worker_loop(self):
        """Main worker loop that polls for new posts."""
        logger.info("Starting polling worker loop...")

        while not self._stop_event.is_set():
            try:
                # Fetch recent posts
                try:
                    posts = self._fetch_recent_posts()
                    self._consecutive_errors = 0
                except Exception:
                    self._consecutive_errors += 1
                    backoff = min(
                        self._max_backoff,
                        self._base_backoff * (2 ** (self._consecutive_errors - 1)),
                    )
                    logger.warning(
                        "Fetch error count=%s; backing off %.1fs",
                        self._consecutive_errors,
                        backoff,
                    )
                    self._stop_event.wait(backoff)
                    continue

                if posts:
                    # Save to database
                    result = self.db_manager.save_posts(posts)

                    if result["new"] > 0:
                        with self._stats_lock:
                            self.posts_saved += result["new"]
                        logger.info(f"Saved {result['new']} new posts")

                # Update last check time & persist stream state
                now = datetime.now(timezone.utc)
                self.last_check = now
                try:
                    if posts:
                        # Save last stream time for continuity
                        if self._last_stream_time:
                            self.db_manager.set_metadata(
                                "last_stream_time", self._last_stream_time.isoformat()
                            )
                except Exception as e:
                    logger.debug(f"Could not persist stream metadata: {e}")

                # Wait for next poll or stop event
                self._stop_event.wait(self.poll_interval)

            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                self._consecutive_errors += 1
                backoff = min(
                    self._max_backoff,
                    self._base_backoff * (2 ** (self._consecutive_errors - 1)),
                )
                self._stop_event.wait(backoff)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current streaming statistics.

        Returns:
            Dictionary containing streaming statistics
        """
        with self._stats_lock:
            runtime = None
            if self.start_time:
                runtime = (datetime.now(timezone.utc) - self.start_time).total_seconds()

            posts_per_minute = 0
            if runtime and runtime > 0:
                posts_per_minute = (self.posts_processed / runtime) * 60

            return {
                "is_running": self.is_running,
                "start_time": self.start_time,
                "runtime_seconds": runtime,
                "posts_processed": self.posts_processed,
                "posts_saved": self.posts_saved,
                "posts_per_minute": round(posts_per_minute, 2),
                "last_check": self.last_check,
                "poll_interval": self.poll_interval,
                "filters": {
                    "user_handles": list(self.user_handles),
                    "keywords": list(self.keywords),
                },
                "error_streak": self._consecutive_errors,
                "last_stream_time": self._last_stream_time,
                "last_cursor": self._last_cursor,
            }

    def start(self):
        """Start the streaming service."""
        if self.is_running:
            logger.warning("Streaming service is already running")
            return

        logger.info("Starting Bluesky streaming service...")

        # Initialize statistics
        self.start_time = datetime.now(timezone.utc)
        self.posts_processed = 0
        self.posts_saved = 0
        self.is_running = True
        self._stop_event.clear()

        # Log configuration
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        if self.user_handles:
            logger.info(f"Following specific users: {', '.join(self.user_handles)}")
        if self.keywords:
            logger.info(f"Filtering by keywords: {', '.join(self.keywords)}")
        if not self.user_handles and not self.keywords:
            logger.info("Processing timeline posts (no specific filters applied)")

        # Authenticate with retry/backoff
        auth_attempts = 0
        while auth_attempts < 3 and not self._authenticate():
            auth_attempts += 1
            wait_for = min(30, 2**auth_attempts)
            logger.warning(
                "Authentication attempt %s failed; retrying in %ss",
                auth_attempts,
                wait_for,
            )
            time.sleep(wait_for)
        if not self._authenticated:
            self.is_running = False
            raise RuntimeError("Failed to authenticate with Bluesky after retries")

        # Load previous stream time if exists
        try:
            prev_time = self.db_manager.get_metadata("last_stream_time")
            if prev_time:
                self._last_stream_time = datetime.fromisoformat(prev_time)
            prev_cursor = self.db_manager.get_metadata("last_stream_cursor")
            if prev_cursor:
                self._last_cursor = prev_cursor
        except Exception:
            pass

        try:
            # Start worker thread
            self._worker_thread = threading.Thread(
                target=self._worker_loop, daemon=True
            )
            self._worker_thread.start()

            # Wait for stop signal
            try:
                while self.is_running and self._worker_thread.is_alive():
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, stopping...")
                self.stop()

        except Exception as e:
            logger.error(f"Streaming service error: {e}")
            self.stop()
            raise

    def stop(self):
        """Stop the streaming service."""
        if not self.is_running:
            return

        logger.info("Stopping streaming service...")
        self.is_running = False
        self._stop_event.set()

        # Wait for worker thread to finish
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)

        # Log final statistics
        stats = self.get_stats()
        logger.info("Streaming session completed:")
        logger.info(f"  Runtime: {stats['runtime_seconds']:.1f} seconds")
        logger.info(f"  Posts processed: {stats['posts_processed']}")
        logger.info(f"  Posts saved: {stats['posts_saved']}")
        logger.info(f"  Processing rate: {stats['posts_per_minute']:.1f} posts/minute")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
