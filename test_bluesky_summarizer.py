"""
Tests for the Bluesky Feed Summarizer application.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import tempfile
import os

from src.bluesky_summarizer.bluesky.client import BlueSkyClient
from src.bluesky_summarizer.database.models import Post, Summary
from src.bluesky_summarizer.database.operations import DatabaseManager
from src.bluesky_summarizer.ai.summarizer import ClaudeSummarizer


class TestDatetimeComparison:
    """Test datetime timezone handling and comparisons."""

    def test_timezone_aware_datetime_comparison(self):
        """Test that timezone-aware datetimes can be compared without errors."""
        # Create timezone-aware datetimes
        start_date = datetime.now(timezone.utc)
        end_date = datetime.now(timezone.utc) + timedelta(hours=1)
        created_at = datetime.fromisoformat(
            "2024-01-01T12:00:00Z".replace("Z", "+00:00")
        )

        # These comparisons should work without TypeError
        assert created_at < start_date
        assert created_at < end_date
        assert start_date < end_date

    def test_timezone_naive_conversion(self):
        """Test conversion of naive datetimes to timezone-aware."""
        # Create naive datetime
        naive_dt = datetime(2024, 1, 1, 12, 0, 0)
        assert naive_dt.tzinfo is None

        # Convert to timezone-aware
        aware_dt = naive_dt.replace(tzinfo=timezone.utc)
        assert aware_dt.tzinfo is not None
        assert aware_dt.tzinfo == timezone.utc

    def test_mixed_datetime_comparison_fails(self):
        """Test that comparing naive and aware datetimes raises TypeError."""
        naive_dt = datetime(2024, 1, 1, 12, 0, 0)
        aware_dt = datetime.now(timezone.utc)

        with pytest.raises(
            TypeError, match="can't compare offset-naive and offset-aware datetimes"
        ):
            naive_dt < aware_dt


class TestBlueSkyClient:
    """Test the BlueSky API client."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = BlueSkyClient("test.bsky.social", "test_password")

    def test_client_initialization(self):
        """Test client is properly initialized."""
        assert self.client.handle == "test.bsky.social"
        assert self.client.password == "test_password"
        assert not self.client._authenticated

    @patch("src.bluesky_summarizer.bluesky.client.Client")
    def test_authentication_success(self, mock_client_class):
        """Test successful authentication."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.login.return_value = True

        client = BlueSkyClient("test.bsky.social", "test_password")
        client.client = mock_client

        result = client.authenticate()

        assert result is True
        assert client._authenticated is True
        mock_client.login.assert_called_once_with("test.bsky.social", "test_password")

    @patch("src.bluesky_summarizer.bluesky.client.Client")
    def test_authentication_failure(self, mock_client_class):
        """Test authentication failure."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.login.side_effect = Exception("Authentication failed")

        client = BlueSkyClient("test.bsky.social", "test_password")
        client.client = mock_client

        result = client.authenticate()

        assert result is False
        assert client._authenticated is False

    def test_timezone_normalization_in_fetch(self):
        """Test that fetch_timeline_posts normalizes timezone-naive datetimes."""
        # Create timezone-naive datetimes
        start_date = datetime(2024, 1, 1, 0, 0, 0)
        end_date = datetime(2024, 1, 2, 0, 0, 0)

        assert start_date.tzinfo is None
        assert end_date.tzinfo is None

        with patch.object(self.client, "authenticate", return_value=True):
            with patch.object(self.client.client, "get_timeline") as mock_get_timeline:
                # Mock empty response to avoid actual API call
                mock_response = Mock()
                mock_response.feed = []
                mock_response.cursor = None
                mock_get_timeline.return_value = mock_response

                # This should not raise a TypeError
                result = self.client.fetch_timeline_posts(start_date, end_date)

                assert isinstance(result, list)
                assert len(result) == 0

    def test_post_conversion(self):
        """Test conversion of AT Protocol post to our Post model."""
        # Create mock AT Protocol post
        mock_author = Mock()
        mock_author.handle = "test.bsky.social"
        mock_author.did = "did:plc:test123"

        mock_record = Mock()
        mock_record.text = "Test post content"

        mock_atproto_post = Mock()
        mock_atproto_post.uri = "at://test/post/123"
        mock_atproto_post.cid = "cid123"
        mock_atproto_post.author = mock_author
        mock_atproto_post.record = mock_record
        mock_atproto_post.like_count = 5
        mock_atproto_post.repost_count = 2
        mock_atproto_post.reply_count = 1

        created_at = datetime.now(timezone.utc)

        post = self.client._convert_to_post_model(mock_atproto_post, created_at)

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

    def test_post_model_creation(self):
        """Test Post model creation with Pydantic."""
        now = datetime.now(timezone.utc)

        post = Post(
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

    def test_post_model_validation(self):
        """Test Post model validation."""
        now = datetime.now(timezone.utc)

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

    def test_post_datetime_parsing(self):
        """Test Post model datetime string parsing."""
        post_data = {
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

        post = Post(**post_data)

        assert isinstance(post.created_at, datetime)
        assert isinstance(post.indexed_at, datetime)
        assert post.created_at.tzinfo is not None
        assert post.indexed_at.tzinfo is not None

    def test_summary_model_creation(self):
        """Test Summary model creation."""
        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=1)
        created_at = datetime.now(timezone.utc)

        summary = Summary(
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

    def setup_method(self):
        """Set up test database."""
        # Use temporary file for testing to avoid connection issues with in-memory DB
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_manager = DatabaseManager(self.temp_db.name)

    def teardown_method(self):
        """Clean up test database."""
        # Remove temporary database file
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_database_initialization(self):
        """Test database tables are created."""
        # Tables should be created during initialization
        # This test passes if no exceptions are raised
        assert self.db_manager.db_path.endswith(".db")

    def test_save_and_retrieve_post(self):
        """Test saving and retrieving a post."""
        now = datetime.now(timezone.utc)

        post = Post(
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
        post_id = self.db_manager.save_post(post)
        assert post_id is not None

        # Retrieve posts
        start_date = now - timedelta(hours=1)
        end_date = now + timedelta(hours=1)
        posts = self.db_manager.get_posts_by_date_range(start_date, end_date)

        assert len(posts) == 1
        retrieved_post = posts[0]
        assert retrieved_post.uri == "at://test/post/123"
        assert retrieved_post.text == "Test post"

    def test_save_and_retrieve_summary(self):
        """Test saving and retrieving a summary."""
        now = datetime.now(timezone.utc)

        summary = Summary(
            start_date=now - timedelta(days=1),
            end_date=now,
            post_count=5,
            summary_text="Test summary",
            model_used="claude-3-7-sonnet-latest",
            created_at=now,
        )

        # Save summary
        summary_id = self.db_manager.save_summary(summary)
        assert summary_id is not None

        # Retrieve latest summary
        latest_summary = self.db_manager.get_latest_summary()
        assert latest_summary is not None
        assert latest_summary.summary_text == "Test summary"
        assert latest_summary.post_count == 5


class TestClaudeSummarizer:
    """Test Claude AI summarizer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.summarizer = ClaudeSummarizer("test_api_key", "claude-3-7-sonnet-latest")

    def test_summarizer_initialization(self):
        """Test summarizer is properly initialized."""
        assert self.summarizer.model == "claude-3-7-sonnet-latest"

    def test_empty_posts_summary(self):
        """Test summary generation with empty posts list."""
        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=1)

        summary = self.summarizer.summarize_posts([], start_date, end_date)

        assert isinstance(summary, Summary)
        assert summary.post_count == 0
        assert "No posts found" in summary.summary_text
        assert summary.model_used == "claude-3-7-sonnet-latest"
        assert summary.created_at.tzinfo == timezone.utc

    def test_posts_formatting(self):
        """Test posts formatting for summarization."""
        now = datetime.now(timezone.utc)

        posts = [
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

        formatted_text = self.summarizer._format_posts_for_summarization(posts)

        assert "Post 1:" in formatted_text
        assert "Post 2:" in formatted_text
        assert "user1.bsky.social" in formatted_text
        assert "user2.bsky.social" in formatted_text
        assert "First test post" in formatted_text
        assert "Second test post" in formatted_text
        assert "3 likes" in formatted_text
        assert "5 likes" in formatted_text

    @patch("src.bluesky_summarizer.ai.summarizer.Anthropic")
    def test_summary_generation_with_mock(self, mock_anthropic_class):
        """Test summary generation with mocked Claude API."""
        # Mock the Anthropic client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock the API response
        mock_response = Mock()
        mock_content = Mock()
        mock_content.text = "This is a test summary of the posts."
        mock_response.content = [mock_content]
        mock_client.messages.create.return_value = mock_response

        # Create test posts
        now = datetime.now(timezone.utc)
        posts = [
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

        # Create summarizer with mocked client
        summarizer = ClaudeSummarizer("test_api_key", "claude-3-7-sonnet-latest")
        summarizer.client = mock_client

        # Generate summary
        start_date = now - timedelta(hours=1)
        end_date = now + timedelta(hours=1)
        summary = summarizer.summarize_posts(posts, start_date, end_date)

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

    def test_datetime_consistency_across_components(self):
        """Test that all components handle timezones consistently."""
        # Create timezone-aware datetime
        now = datetime.now(timezone.utc)

        # Test Post model
        post = Post(
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
        summary = Summary(
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
