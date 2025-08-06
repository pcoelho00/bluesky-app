"""
Tests for the Bluesky Feed Summarizer application.
"""

import pytest
from datetime import datetime, timezone, timedelta
import os
from typing import List
from unittest.mock import Mock

from bluesky_summarizer.bluesky.client import BlueSkyClient
from bluesky_summarizer.database.models import Post, Summary
from bluesky_summarizer.database.operations import DatabaseManager
from bluesky_summarizer.ai.summarizer import ClaudeSummarizer

# Global test database path
TEST_DB_PATH = "test_database.db"


def setup_module() -> None:
    """Set up module-level fixtures."""
    # Clean up any existing test database
    if os.path.exists(TEST_DB_PATH):
        os.unlink(TEST_DB_PATH)


def teardown_module() -> None:
    """Clean up module-level fixtures."""
    # Remove test database after all tests
    if os.path.exists(TEST_DB_PATH):
        os.unlink(TEST_DB_PATH)


class TestDatetimeComparison:
    """Test datetime timezone handling and comparisons."""

    def test_timezone_aware_datetime_comparison(self) -> None:
        """Test that timezone-aware datetimes can be compared without errors."""
        # Create timezone-aware datetimes
        start_date: datetime = datetime.now(timezone.utc)
        end_date: datetime = datetime.now(timezone.utc) + timedelta(hours=1)
        created_at: datetime = datetime.fromisoformat(
            "2024-01-01T12:00:00Z".replace("Z", "+00:00")
        )

        # These comparisons should work without TypeError
        assert created_at < start_date
        assert created_at < end_date
        assert start_date < end_date

    def test_timezone_naive_conversion(self) -> None:
        """Test conversion of naive datetimes to timezone-aware."""
        # Create naive datetime
        naive_dt: datetime = datetime(2024, 1, 1, 12, 0, 0)
        assert naive_dt.tzinfo is None

        # Convert to timezone-aware
        aware_dt: datetime = naive_dt.replace(tzinfo=timezone.utc)
        assert aware_dt.tzinfo is not None
        assert aware_dt.tzinfo == timezone.utc

    def test_mixed_datetime_comparison_fails(self) -> None:
        """Test that comparing naive and aware datetimes raises TypeError."""
        naive_dt: datetime = datetime(2024, 1, 1, 12, 0, 0)
        aware_dt: datetime = datetime.now(timezone.utc)

        with pytest.raises(
            TypeError, match="can't compare offset-naive and offset-aware datetimes"
        ):
            naive_dt < aware_dt


class TestBlueSkyClient:
    """Test the BlueSky API client."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.client: BlueSkyClient = BlueSkyClient("test.bsky.social", "test_password")

    def test_client_initialization(self) -> None:
        """Test client is properly initialized."""
        assert self.client.handle == "test.bsky.social"
        assert self.client.password == "test_password"
        assert not self.client._authenticated

    def test_authentication_simulation(self) -> None:
        """Test authentication logic simulation."""
        # Create a mock client object
        mock_client = Mock()
        mock_client.login.return_value = True

        # Replace the client
        self.client.client = mock_client

        # Test successful authentication
        result: bool = self.client.authenticate()

        assert result is True
        assert self.client._authenticated is True
        mock_client.login.assert_called_once_with("test.bsky.social", "test_password")

    def test_authentication_failure_simulation(self) -> None:
        """Test authentication failure simulation."""
        # Create a mock client that raises an exception
        mock_client = Mock()
        mock_client.login.side_effect = Exception("Authentication failed")

        # Replace the client
        self.client.client = mock_client

        # Test authentication failure
        result: bool = self.client.authenticate()

        assert result is False
        assert self.client._authenticated is False

    def test_timezone_normalization_in_fetch(self) -> None:
        """Test that fetch_timeline_posts normalizes timezone-naive datetimes."""
        # Create timezone-naive datetimes
        start_date: datetime = datetime(2024, 1, 1, 0, 0, 0)
        end_date: datetime = datetime(2024, 1, 2, 0, 0, 0)

        assert start_date.tzinfo is None
        assert end_date.tzinfo is None

        # Mock the authentication and get_timeline methods
        def mock_authenticate() -> bool:
            return True

        def mock_get_timeline(**kwargs) -> Mock:
            mock_response = Mock()
            mock_response.feed = []
            mock_response.cursor = None
            return mock_response

        # Replace the methods
        self.client.authenticate = mock_authenticate
        self.client.client = Mock()
        self.client.client.get_timeline = mock_get_timeline

        # This should not raise a TypeError
        result: List[Post] = self.client.fetch_timeline_posts(start_date, end_date)

        assert isinstance(result, list)
        assert len(result) == 0

    def test_post_conversion(self) -> None:
        """Test conversion of AT Protocol post to our Post model."""
        # Create mock AT Protocol post
        mock_author: Mock = Mock()
        mock_author.handle = "test.bsky.social"
        mock_author.did = "did:plc:test123"

        mock_record: Mock = Mock()
        mock_record.text = "Test post content"

        mock_atproto_post: Mock = Mock()
        mock_atproto_post.uri = "at://test/post/123"
        mock_atproto_post.cid = "cid123"
        mock_atproto_post.author = mock_author
        mock_atproto_post.record = mock_record
        mock_atproto_post.like_count = 5
        mock_atproto_post.repost_count = 2
        mock_atproto_post.reply_count = 1

        created_at: datetime = datetime.now(timezone.utc)

        post: Post = self.client._convert_to_post_model(mock_atproto_post, created_at)

        assert isinstance(post, Post)
        assert post.uri == "at://test/post/123"
        assert post.cid == "cid123"
        assert post.author_handle == "test.bsky.social"
        assert post.author_did == "did:plc:test123"
        assert post.text == "Test post content"
        assert post.created_at == created_at
        assert post.like_count == 5
        assert post.repost_count == 2
        assert post.reply_count == 1
        assert post.indexed_at.tzinfo == timezone.utc


class TestDatabaseModels:
    """Test Pydantic database models."""

    def test_post_model_creation(self) -> None:
        """Test Post model creation with Pydantic."""
        now: datetime = datetime.now(timezone.utc)

        post: Post = Post(
            uri="at://test/post/123",
            cid="cid123",
            author_handle="test.bsky.social",
            author_did="did:plc:test123",
            text="Test post",
            created_at=now,
            like_count=5,
            repost_count=2,
            reply_count=1,
            indexed_at=now,
        )

        assert post.uri == "at://test/post/123"
        assert post.like_count == 5
        assert post.created_at.tzinfo == timezone.utc

    def test_post_model_validation(self) -> None:
        """Test Post model validation."""
        now: datetime = datetime.now(timezone.utc)

        # Test that negative counts are not allowed
        with pytest.raises(ValueError):
            Post(
                uri="at://test/post/123",
                cid="cid123",
                author_handle="test.bsky.social",
                author_did="did:plc:test123",
                text="Test post",
                created_at=now,
                like_count=-1,  # Should fail validation
                repost_count=2,
                reply_count=1,
                indexed_at=now,
            )

    def test_post_datetime_parsing(self) -> None:
        """Test Post model datetime string parsing."""
        post_data: dict[str, str | int] = {
            "uri": "at://test/post/123",
            "cid": "cid123",
            "author_handle": "test.bsky.social",
            "author_did": "did:plc:test123",
            "text": "Test post",
            "created_at": "2024-01-01T12:00:00Z",
            "like_count": 5,
            "repost_count": 2,
            "reply_count": 1,
            "indexed_at": "2024-01-01T12:00:00Z",
        }

        post: Post = Post(**post_data)

        assert isinstance(post.created_at, datetime)
        assert isinstance(post.indexed_at, datetime)
        assert post.created_at.tzinfo is not None
        assert post.indexed_at.tzinfo is not None

    def test_summary_model_creation(self) -> None:
        """Test Summary model creation."""
        start_date: datetime = datetime.now(timezone.utc)
        end_date: datetime = start_date + timedelta(days=1)
        created_at: datetime = datetime.now(timezone.utc)

        summary: Summary = Summary(
            start_date=start_date,
            end_date=end_date,
            post_count=10,
            summary_text="Test summary",
            model_used="claude-3-7-sonnet-latest",
            created_at=created_at,
        )

        assert summary.post_count == 10
        assert summary.summary_text == "Test summary"
        assert summary.model_used == "claude-3-7-sonnet-latest"
        assert summary.start_date.tzinfo == timezone.utc


class TestDatabaseOperations:
    """Test database operations."""

    def setup_method(self) -> None:
        """Set up test database."""
        # Use the shared test database path
        self.db_manager: DatabaseManager = DatabaseManager(TEST_DB_PATH)
        # Clean database before each test
        self._clean_database()

    def _clean_database(self) -> None:
        """Clean all data from the test database."""
        import sqlite3

        with sqlite3.connect(self.db_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM posts")
            cursor.execute("DELETE FROM summaries")
            conn.commit()

    def test_database_initialization(self) -> None:
        """Test database tables are created."""
        # Tables should be created during initialization
        # This test passes if no exceptions are raised
        assert self.db_manager.db_path == TEST_DB_PATH

    def test_save_and_retrieve_post(self) -> None:
        """Test saving and retrieving a post."""
        now: datetime = datetime.now(timezone.utc)

        post: Post = Post(
            uri="at://test/post/123",
            cid="cid123",
            author_handle="test.bsky.social",
            author_did="did:plc:test123",
            text="Test post",
            created_at=now,
            like_count=5,
            repost_count=2,
            reply_count=1,
            indexed_at=now,
        )

        # Save post
        post_id: int = self.db_manager.save_post(post)
        assert post_id is not None

        # Retrieve posts
        start_date: datetime = now - timedelta(hours=1)
        end_date: datetime = now + timedelta(hours=1)
        posts: List[Post] = self.db_manager.get_posts_by_date_range(
            start_date, end_date
        )

        assert len(posts) == 1
        retrieved_post: Post = posts[0]
        assert retrieved_post.uri == "at://test/post/123"
        assert retrieved_post.text == "Test post"

    def test_save_and_retrieve_summary(self) -> None:
        """Test saving and retrieving a summary."""
        now: datetime = datetime.now(timezone.utc)

        summary: Summary = Summary(
            start_date=now - timedelta(days=1),
            end_date=now,
            post_count=5,
            summary_text="Test summary",
            model_used="claude-3-7-sonnet-latest",
            created_at=now,
        )

        # Save summary
        summary_id: int = self.db_manager.save_summary(summary)
        assert summary_id is not None

        # Retrieve latest summary
        latest_summary: Summary | None = self.db_manager.get_latest_summary()
        assert latest_summary is not None
        assert latest_summary.summary_text == "Test summary"
        assert latest_summary.post_count == 5

    def test_post_uniqueness_by_uri(self) -> None:
        """Test that posts are unique by URI."""
        now: datetime = datetime.now(timezone.utc)

        # Create two posts with the same URI but different content
        post1: Post = Post(
            uri="at://test/post/unique",
            cid="cid1",
            author_handle="test.bsky.social",
            author_did="did:plc:test123",
            text="Original post text",
            created_at=now,
            like_count=5,
            repost_count=2,
            reply_count=1,
            indexed_at=now,
        )

        post2: Post = Post(
            uri="at://test/post/unique",  # Same URI
            cid="cid2",
            author_handle="test.bsky.social",
            author_did="did:plc:test123",
            text="Updated post text",
            created_at=now,
            like_count=10,  # Different metrics
            repost_count=5,
            reply_count=3,
            indexed_at=now,
        )

        # Save first post
        result1: dict[str, int] = self.db_manager.save_posts([post1])
        assert result1["new"] == 1
        assert result1["updated"] == 0

        # Save second post with same URI (should update, not create new)
        result2: dict[str, int] = self.db_manager.save_posts([post2])
        assert result2["new"] == 0
        assert result2["updated"] == 1

        # Verify only one post exists
        total_posts: int = self.db_manager.get_total_post_count()
        assert total_posts == 1

        # Verify the post was updated with new content
        start_date: datetime = now - timedelta(hours=1)
        end_date: datetime = now + timedelta(hours=1)
        posts: List[Post] = self.db_manager.get_posts_by_date_range(
            start_date, end_date
        )

        assert len(posts) == 1
        updated_post: Post = posts[0]
        assert updated_post.uri == "at://test/post/unique"
        assert updated_post.text == "Updated post text"
        assert updated_post.like_count == 10

    def test_bulk_save_with_duplicates(self) -> None:
        """Test bulk saving posts with some duplicates."""
        now: datetime = datetime.now(timezone.utc)

        posts: List[Post] = [
            Post(
                uri="at://test/post/1",
                cid="cid1",
                author_handle="user1.bsky.social",
                author_did="did:plc:user1",
                text="First post",
                created_at=now,
                like_count=1,
                repost_count=0,
                reply_count=0,
                indexed_at=now,
            ),
            Post(
                uri="at://test/post/2",
                cid="cid2",
                author_handle="user2.bsky.social",
                author_did="did:plc:user2",
                text="Second post",
                created_at=now,
                like_count=2,
                repost_count=0,
                reply_count=0,
                indexed_at=now,
            ),
            Post(
                uri="at://test/post/1",  # Duplicate URI
                cid="cid1_updated",
                author_handle="user1.bsky.social",
                author_did="did:plc:user1",
                text="Updated first post",
                created_at=now,
                like_count=5,
                repost_count=1,
                reply_count=0,
                indexed_at=now,
            ),
        ]

        # Save all posts
        result: dict[str, int] = self.db_manager.save_posts(posts)

        # Should have 2 new posts and 1 update (the duplicate URI)
        assert result["new"] == 2
        assert result["updated"] == 1
        assert result["total"] == 3

        # Verify database state
        total_posts: int = self.db_manager.get_total_post_count()
        unique_uris: int = self.db_manager.get_unique_uri_count()

        assert total_posts == 2  # Only 2 unique posts
        assert unique_uris == 2  # 2 unique URIs
        assert total_posts == unique_uris  # No URI duplicates

    def test_database_integrity_methods(self) -> None:
        """Test database integrity checking methods."""
        now: datetime = datetime.now(timezone.utc)

        # Add some test data
        posts: List[Post] = [
            Post(
                uri="at://test/post/1",
                cid="cid1",
                author_handle="user1.bsky.social",
                author_did="did:plc:user1",
                text="Unique content 1",
                created_at=now,
                like_count=1,
                repost_count=0,
                reply_count=0,
                indexed_at=now,
            ),
            Post(
                uri="at://test/post/2",
                cid="cid2",
                author_handle="user2.bsky.social",
                author_did="did:plc:user2",
                text="Duplicate content",
                created_at=now,
                like_count=2,
                repost_count=0,
                reply_count=0,
                indexed_at=now,
            ),
            Post(
                uri="at://test/post/3",
                cid="cid3",
                author_handle="user3.bsky.social",
                author_did="did:plc:user3",
                text="Duplicate content",  # Same content as post 2
                created_at=now,
                like_count=3,
                repost_count=0,
                reply_count=0,
                indexed_at=now,
            ),
        ]

        self.db_manager.save_posts(posts)

        # Test count methods
        total_posts: int = self.db_manager.get_total_post_count()
        unique_uris: int = self.db_manager.get_unique_uri_count()
        duplicate_content: int = self.db_manager.get_duplicate_content_count()

        assert total_posts == 3
        assert unique_uris == 3
        assert duplicate_content == 1  # One text appears twice

        # Test duplicate detection
        duplicate_uris: List[str] = self.db_manager.find_duplicate_uris()
        assert len(duplicate_uris) == 0  # Should be no URI duplicates due to constraint

        # Test content duplicate detection
        content_duplicates: List[tuple[str, int]] = (
            self.db_manager.get_posts_with_duplicate_content()
        )
        assert len(content_duplicates) == 1
        assert content_duplicates[0][0] == "Duplicate content"
        assert content_duplicates[0][1] == 2  # Appears twice


class TestClaudeSummarizer:
    """Test Claude AI summarizer."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.summarizer: ClaudeSummarizer = ClaudeSummarizer(
            "test_api_key", "claude-3-7-sonnet-latest"
        )

    def test_summarizer_initialization(self) -> None:
        """Test summarizer is properly initialized."""
        assert self.summarizer.model == "claude-3-7-sonnet-latest"

    def test_empty_posts_summary(self) -> None:
        """Test summary generation with empty posts list."""
        start_date: datetime = datetime.now(timezone.utc)
        end_date: datetime = start_date + timedelta(days=1)

        summary: Summary = self.summarizer.summarize_posts([], start_date, end_date)

        assert isinstance(summary, Summary)
        assert summary.post_count == 0
        assert "No posts found" in summary.summary_text
        assert summary.model_used == "claude-3-7-sonnet-latest"
        assert summary.created_at.tzinfo == timezone.utc

    def test_posts_formatting(self) -> None:
        """Test posts formatting for summarization."""
        now: datetime = datetime.now(timezone.utc)

        posts: List[Post] = [
            Post(
                uri="at://test/post/1",
                cid="cid1",
                author_handle="user1.bsky.social",
                author_did="did:plc:user1",
                text="First test post",
                created_at=now,
                like_count=3,
                repost_count=1,
                reply_count=0,
                indexed_at=now,
            ),
            Post(
                uri="at://test/post/2",
                cid="cid2",
                author_handle="user2.bsky.social",
                author_did="did:plc:user2",
                text="Second test post",
                created_at=now + timedelta(minutes=30),
                like_count=5,
                repost_count=2,
                reply_count=1,
                indexed_at=now,
            ),
        ]

        formatted_text: str = self.summarizer._format_posts_for_summarization(posts)

        assert "Post 1:" in formatted_text
        assert "Post 2:" in formatted_text
        assert "user1.bsky.social" in formatted_text
        assert "user2.bsky.social" in formatted_text
        assert "First test post" in formatted_text
        assert "Second test post" in formatted_text
        assert "3 likes" in formatted_text
        assert "5 likes" in formatted_text

    def test_summary_generation_with_mock_simulation(self) -> None:
        """Test summary generation with simulated Claude API."""
        # Create a mock client
        mock_client = Mock()

        # Mock the API response
        mock_response = Mock()
        mock_content = Mock()
        mock_content.text = "This is a test summary of the posts."
        mock_response.content = [mock_content]
        mock_client.messages.create.return_value = mock_response

        # Create test posts
        now: datetime = datetime.now(timezone.utc)
        posts: List[Post] = [
            Post(
                uri="at://test/post/1",
                cid="cid1",
                author_handle="user1.bsky.social",
                author_did="did:plc:user1",
                text="Test post content",
                created_at=now,
                like_count=3,
                repost_count=1,
                reply_count=0,
                indexed_at=now,
            )
        ]

        # Replace the client
        self.summarizer.client = mock_client

        # Generate summary
        start_date: datetime = now - timedelta(hours=1)
        end_date: datetime = now + timedelta(hours=1)
        summary: Summary = self.summarizer.summarize_posts(posts, start_date, end_date)

        # Verify results
        assert isinstance(summary, Summary)
        assert summary.post_count == 1
        assert summary.summary_text == "This is a test summary of the posts."
        assert summary.model_used == "claude-3-7-sonnet-latest"
        assert summary.created_at.tzinfo == timezone.utc

        # Verify API was called correctly
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args
        assert call_args[1]["model"] == "claude-3-7-sonnet-latest"
        assert call_args[1]["max_tokens"] == 1000
        assert call_args[1]["temperature"] == 0.3


# Integration tests
class TestIntegration:
    """Integration tests for the complete workflow."""

    def test_datetime_consistency_across_components(self) -> None:
        """Test that all components handle timezones consistently."""
        # Create timezone-aware datetime
        now: datetime = datetime.now(timezone.utc)

        # Test Post model
        post: Post = Post(
            uri="at://test/post/123",
            cid="cid123",
            author_handle="test.bsky.social",
            author_did="did:plc:test123",
            text="Test post",
            created_at=now,
            like_count=5,
            repost_count=2,
            reply_count=1,
            indexed_at=now,
        )

        # Test Summary model
        summary: Summary = Summary(
            start_date=now - timedelta(days=1),
            end_date=now,
            post_count=1,
            summary_text="Test summary",
            model_used="claude-3-7-sonnet-latest",
            created_at=now,
        )

        # All datetime comparisons should work
        assert post.created_at <= summary.end_date
        assert post.created_at >= summary.start_date
        assert summary.start_date < summary.end_date
        assert summary.created_at.tzinfo == timezone.utc
        assert post.created_at.tzinfo == timezone.utc

    def test_posts_chronological_ordering(self) -> None:
        """Test that posts are returned in chronological order."""
        # Create test posts with different timestamps
        now: datetime = datetime.now(timezone.utc)

        posts: List[Post] = [
            Post(
                uri="at://test/post/3",
                cid="cid3",
                author_handle="user3.bsky.social",
                author_did="did:plc:user3",
                text="Latest post",
                created_at=now,
                like_count=1,
                repost_count=0,
                reply_count=0,
                indexed_at=now,
            ),
            Post(
                uri="at://test/post/1",
                cid="cid1",
                author_handle="user1.bsky.social",
                author_did="did:plc:user1",
                text="Oldest post",
                created_at=now - timedelta(hours=2),
                like_count=3,
                repost_count=1,
                reply_count=0,
                indexed_at=now,
            ),
            Post(
                uri="at://test/post/2",
                cid="cid2",
                author_handle="user2.bsky.social",
                author_did="did:plc:user2",
                text="Middle post",
                created_at=now - timedelta(hours=1),
                like_count=2,
                repost_count=0,
                reply_count=1,
                indexed_at=now,
            ),
        ]

        # Sort chronologically (oldest first)
        sorted_posts: List[Post] = sorted(posts, key=lambda p: p.created_at)

        # Verify chronological order
        assert len(sorted_posts) == 3
        assert sorted_posts[0].text == "Oldest post"
        assert sorted_posts[1].text == "Middle post"
        assert sorted_posts[2].text == "Latest post"

        # Verify timestamps are in ascending order
        assert sorted_posts[0].created_at < sorted_posts[1].created_at
        assert sorted_posts[1].created_at < sorted_posts[2].created_at

    def test_posts_author_filtering(self) -> None:
        """Test that posts can be filtered by author handle."""
        now: datetime = datetime.now(timezone.utc)

        posts: List[Post] = [
            Post(
                uri="at://test/post/1",
                cid="cid1",
                author_handle="alice.bsky.social",
                author_did="did:plc:alice",
                text="Alice's post",
                created_at=now,
                like_count=1,
                repost_count=0,
                reply_count=0,
                indexed_at=now,
            ),
            Post(
                uri="at://test/post/2",
                cid="cid2",
                author_handle="bob.bsky.social",
                author_did="did:plc:bob",
                text="Bob's post",
                created_at=now,
                like_count=2,
                repost_count=0,
                reply_count=0,
                indexed_at=now,
            ),
            Post(
                uri="at://test/post/3",
                cid="cid3",
                author_handle="alice.bsky.social",
                author_did="did:plc:alice",
                text="Another Alice post",
                created_at=now,
                like_count=3,
                repost_count=0,
                reply_count=0,
                indexed_at=now,
            ),
        ]

        # Filter by author (case-insensitive partial match)
        author_filter: str = "alice"
        filtered_posts: List[Post] = [
            post
            for post in posts
            if author_filter.lower() in post.author_handle.lower()
        ]

        # Verify filtering works
        assert len(filtered_posts) == 2
        assert all("alice" in post.author_handle.lower() for post in filtered_posts)
        assert filtered_posts[0].text == "Alice's post"
        assert filtered_posts[1].text == "Another Alice post"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
