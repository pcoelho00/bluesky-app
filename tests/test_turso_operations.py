"""
Tests for Turso database operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from bluesky_summarizer.database.turso_operations import TursoDatabaseManager
from bluesky_summarizer.database.models import Post, Summary


class TestTursoDatabaseManager:
    """Test the TursoDatabaseManager class."""

    def setup_method(self):
        """Set up for each test method."""
        self.mock_client = MagicMock()

        # Mock the libsql_client module
        self.libsql_patcher = patch(
            "bluesky_summarizer.database.turso_operations.libsql_client"
        )
        self.mock_libsql = self.libsql_patcher.start()
        self.mock_libsql.create_client.return_value = self.mock_client

        self.manager = TursoDatabaseManager("libsql://test.turso.io", "test_token")

    def teardown_method(self):
        """Clean up after each test method."""
        self.libsql_patcher.stop()

    def test_init_creates_client_and_initializes_schema(self):
        """Test that initialization creates client and initializes schema."""
        self.mock_libsql.create_client.assert_called_once_with(
            url="libsql://test.turso.io", auth_token="test_token"
        )

        # Check that schema initialization commands were executed
        execute_calls = self.mock_client.execute.call_args_list
        assert len(execute_calls) > 0

        # Check for table creation calls
        executed_sql = [call[0][0] for call in execute_calls]
        assert any("CREATE TABLE IF NOT EXISTS metadata" in sql for sql in executed_sql)
        assert any("CREATE TABLE IF NOT EXISTS posts" in sql for sql in executed_sql)
        assert any(
            "CREATE TABLE IF NOT EXISTS summaries" in sql for sql in executed_sql
        )

    def test_save_post(self):
        """Test saving a post to Turso database."""
        # Mock the execute response
        mock_result = MagicMock()
        mock_result.last_insert_rowid = 123
        self.mock_client.execute.return_value = mock_result

        post = Post(
            uri="at://test.com/posts/123",
            cid="test_cid",
            author_handle="test.bsky.social",
            author_did="did:plc:test123",
            text="Test post content",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            like_count=5,
            repost_count=2,
            reply_count=1,
        )

        result = self.manager.save_post(post)

        assert result == 123

        # Verify the execute call
        self.mock_client.execute.assert_called_with(
            """
            INSERT OR REPLACE INTO posts
            (uri, cid, author_handle, author_did, text, created_at, 
             like_count, repost_count, reply_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "at://test.com/posts/123",
                "test_cid",
                "test.bsky.social",
                "did:plc:test123",
                "Test post content",
                "2025-01-01T12:00:00",
                5,
                2,
                1,
            ],
        )

    def test_get_posts_by_date_range(self):
        """Test retrieving posts by date range."""
        # Mock the execute response
        mock_result = MagicMock()
        mock_result.rows = [
            [
                "at://test.com/posts/123",
                "test_cid",
                "test.bsky.social",
                "did:plc:test123",
                "Test post content",
                "2025-01-01T12:00:00",
                5,
                2,
                1,
            ]
        ]
        self.mock_client.execute.return_value = mock_result

        start_date = datetime(2025, 1, 1, 0, 0, 0)
        end_date = datetime(2025, 1, 1, 23, 59, 59)

        posts = self.manager.get_posts_by_date_range(start_date, end_date)

        assert len(posts) == 1
        post = posts[0]
        assert post.uri == "at://test.com/posts/123"
        assert post.author_handle == "test.bsky.social"
        assert post.text == "Test post content"
        assert post.like_count == 5

        # Verify the SQL query
        self.mock_client.execute.assert_called_with(
            """
            SELECT uri, cid, author_handle, author_did, text, created_at,
                   like_count, repost_count, reply_count
            FROM posts
            WHERE created_at >= ? AND created_at <= ?
            ORDER BY created_at ASC
            """,
            ["2025-01-01T00:00:00", "2025-01-01T23:59:59"],
        )

    def test_get_posts_by_author_with_date_range(self):
        """Test retrieving posts by author with date range."""
        # Mock the execute response
        mock_result = MagicMock()
        mock_result.rows = []
        self.mock_client.execute.return_value = mock_result

        start_date = datetime(2025, 1, 1, 0, 0, 0)
        end_date = datetime(2025, 1, 1, 23, 59, 59)

        posts = self.manager.get_posts_by_author(
            "test.bsky.social", start_date, end_date
        )

        assert posts == []

        # Verify the SQL query
        self.mock_client.execute.assert_called_with(
            """
                SELECT uri, cid, author_handle, author_did, text, created_at,
                       like_count, repost_count, reply_count
                FROM posts
                WHERE author_handle = ? AND created_at >= ? AND created_at <= ?
                ORDER BY created_at ASC
                """,
            ["test.bsky.social", "2025-01-01T00:00:00", "2025-01-01T23:59:59"],
        )

    def test_get_posts_by_author_without_date_range(self):
        """Test retrieving posts by author without date range."""
        # Mock the execute response
        mock_result = MagicMock()
        mock_result.rows = []
        self.mock_client.execute.return_value = mock_result

        posts = self.manager.get_posts_by_author("test.bsky.social")

        assert posts == []

        # Verify the SQL query
        self.mock_client.execute.assert_called_with(
            """
                SELECT uri, cid, author_handle, author_did, text, created_at,
                       like_count, repost_count, reply_count
                FROM posts
                WHERE author_handle = ?
                ORDER BY created_at ASC
                """,
            ["test.bsky.social"],
        )

    def test_save_summary(self):
        """Test saving a summary to Turso database."""
        # Mock the execute response
        mock_result = MagicMock()
        mock_result.last_insert_rowid = 456
        self.mock_client.execute.return_value = mock_result

        summary = Summary(
            start_date=datetime(2025, 1, 1, 0, 0, 0),
            end_date=datetime(2025, 1, 1, 23, 59, 59),
            post_count=10,
            summary_text="Test summary content",
            model_used="claude-3-haiku-20240307",
            created_at=datetime(2025, 1, 2, 10, 0, 0),
        )

        result = self.manager.save_summary(summary)

        assert result == 456

        # Verify the execute call
        self.mock_client.execute.assert_called_with(
            """
            INSERT INTO summaries
            (start_date, end_date, post_count, summary_text, model_used)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                "2025-01-01T00:00:00",
                "2025-01-01T23:59:59",
                10,
                "Test summary content",
                "claude-3-haiku-20240307",
            ],
        )

    def test_get_summary_by_date_range(self):
        """Test retrieving summary by date range."""
        # Mock the execute response
        mock_result = MagicMock()
        mock_result.rows = [
            [
                "2025-01-01T00:00:00",
                "2025-01-01T23:59:59",
                10,
                "Test summary content",
                "claude-3-haiku-20240307",
                "2025-01-02T10:00:00",
            ]
        ]
        self.mock_client.execute.return_value = mock_result

        start_date = datetime(2025, 1, 1, 0, 0, 0)
        end_date = datetime(2025, 1, 1, 23, 59, 59)

        summary = self.manager.get_summary_by_date_range(start_date, end_date)

        assert summary is not None
        assert summary.post_count == 10
        assert summary.summary_text == "Test summary content"
        assert summary.model_used == "claude-3-haiku-20240307"

    def test_get_summary_by_date_range_not_found(self):
        """Test retrieving summary by date range when not found."""
        # Mock the execute response
        mock_result = MagicMock()
        mock_result.rows = []
        self.mock_client.execute.return_value = mock_result

        start_date = datetime(2025, 1, 1, 0, 0, 0)
        end_date = datetime(2025, 1, 1, 23, 59, 59)

        summary = self.manager.get_summary_by_date_range(start_date, end_date)

        assert summary is None

    def test_get_recent_summaries(self):
        """Test retrieving recent summaries."""
        # Mock the execute response
        mock_result = MagicMock()
        mock_result.rows = [
            [
                "2025-01-02T00:00:00",
                "2025-01-02T23:59:59",
                15,
                "Recent summary content",
                "claude-3-haiku-20240307",
                "2025-01-03T10:00:00",
            ]
        ]
        self.mock_client.execute.return_value = mock_result

        summaries = self.manager.get_recent_summaries(5)

        assert len(summaries) == 1
        summary = summaries[0]
        assert summary.post_count == 15
        assert summary.summary_text == "Recent summary content"

        # Verify the SQL query
        self.mock_client.execute.assert_called_with(
            """
            SELECT start_date, end_date, post_count, summary_text, model_used, created_at
            FROM summaries
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [5],
        )

    def test_get_post_count_with_date_range(self):
        """Test getting post count with date range."""
        # Mock the execute response
        mock_result = MagicMock()
        mock_result.rows = [[25]]
        self.mock_client.execute.return_value = mock_result

        start_date = datetime(2025, 1, 1, 0, 0, 0)
        end_date = datetime(2025, 1, 1, 23, 59, 59)

        count = self.manager.get_post_count(start_date, end_date)

        assert count == 25

        # Verify the SQL query
        self.mock_client.execute.assert_called_with(
            "SELECT COUNT(*) FROM posts WHERE created_at >= ? AND created_at <= ?",
            ["2025-01-01T00:00:00", "2025-01-01T23:59:59"],
        )

    def test_get_post_count_without_date_range(self):
        """Test getting total post count."""
        # Mock the execute response
        mock_result = MagicMock()
        mock_result.rows = [[100]]
        self.mock_client.execute.return_value = mock_result

        count = self.manager.get_post_count()

        assert count == 100

        # Verify the SQL query
        self.mock_client.execute.assert_called_with("SELECT COUNT(*) FROM posts")

    def test_delete_old_posts(self):
        """Test deleting old posts."""
        # Mock the execute response
        mock_result = MagicMock()
        mock_result.rows_affected = 5
        self.mock_client.execute.return_value = mock_result

        cutoff_date = datetime(2024, 12, 1, 0, 0, 0)

        deleted_count = self.manager.delete_old_posts(cutoff_date)

        assert deleted_count == 5

        # Verify the SQL query
        self.mock_client.execute.assert_called_with(
            "DELETE FROM posts WHERE created_at < ?", ["2024-12-01T00:00:00"]
        )

    def test_set_metadata(self):
        """Test setting metadata."""
        self.manager.set_metadata("test_key", "test_value")

        # Verify the SQL query
        self.mock_client.execute.assert_called_with(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ["test_key", "test_value"],
        )

    def test_get_metadata(self):
        """Test getting metadata."""
        # Mock the execute response
        mock_result = MagicMock()
        mock_result.rows = [["test_value"]]
        self.mock_client.execute.return_value = mock_result

        value = self.manager.get_metadata("test_key")

        assert value == "test_value"

        # Verify the SQL query
        self.mock_client.execute.assert_called_with(
            "SELECT value FROM metadata WHERE key = ?", ["test_key"]
        )

    def test_get_metadata_not_found(self):
        """Test getting metadata when key not found."""
        # Mock the execute response
        mock_result = MagicMock()
        mock_result.rows = []
        self.mock_client.execute.return_value = mock_result

        value = self.manager.get_metadata("nonexistent_key")

        assert value is None

    def test_close(self):
        """Test closing the database connection."""
        # Mock client with close method
        self.mock_client.close = Mock()

        self.manager.close()

        self.mock_client.close.assert_called_once()

    def test_close_without_close_method(self):
        """Test closing when client doesn't have close method."""
        # Remove close method if it exists
        if hasattr(self.mock_client, "close"):
            delattr(self.mock_client, "close")

        # This should not raise an error
        self.manager.close()


if __name__ == "__main__":
    pytest.main([__file__])
