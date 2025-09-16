"""
Tests for database environment switching functionality.
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

from bluesky_summarizer.config import (
    DatabaseConfig,
    get_database_environment,
    set_database_environment,
    get_config,
)
from bluesky_summarizer.database.factory import create_database_manager
from bluesky_summarizer.database.operations import DatabaseManager
from bluesky_summarizer.database.turso_operations import TursoDatabaseManager


class TestDatabaseConfig:
    """Test the DatabaseConfig class."""

    def test_is_turso_with_local_environment(self):
        """Test is_turso property returns False for local environment."""
        config = DatabaseConfig(
            db_path="./test.db",
            url="libsql://test.turso.io",
            auth_token="token123",
            environment="local",
        )
        assert not config.is_turso

    def test_is_turso_with_production_environment_and_valid_url(self):
        """Test is_turso property returns True for production with valid URL."""
        config = DatabaseConfig(
            db_path="./test.db",
            url="libsql://test.turso.io",
            auth_token="token123",
            environment="production",
        )
        assert config.is_turso

    def test_is_turso_with_production_environment_and_https_url(self):
        """Test is_turso property returns True for production with HTTPS URL."""
        config = DatabaseConfig(
            db_path="./test.db",
            url="https://test.turso.io",
            auth_token="token123",
            environment="production",
        )
        assert config.is_turso

    def test_is_turso_with_production_environment_but_no_url(self):
        """Test is_turso property returns False for production without URL."""
        config = DatabaseConfig(
            db_path="./test.db", url="", auth_token="token123", environment="production"
        )
        assert not config.is_turso

    def test_is_turso_with_production_environment_but_invalid_url(self):
        """Test is_turso property returns False for production with invalid URL."""
        config = DatabaseConfig(
            db_path="./test.db",
            url="invalid://test.db",
            auth_token="token123",
            environment="production",
        )
        assert not config.is_turso


class TestDatabaseEnvironmentFunctions:
    """Test the database environment management functions."""

    def setup_method(self):
        """Set up for each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

    def teardown_method(self):
        """Clean up after each test method."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)

    def test_get_database_environment_defaults_to_local(self):
        """Test get_database_environment returns 'local' by default."""
        # Clear any existing environment variable
        os.environ.pop("DB_ENVIRONMENT", None)
        assert get_database_environment() == "local"

    def test_get_database_environment_from_env_var(self):
        """Test get_database_environment reads from environment variable."""
        os.environ["DB_ENVIRONMENT"] = "production"
        assert get_database_environment() == "production"

        os.environ["DB_ENVIRONMENT"] = "local"
        assert get_database_environment() == "local"

    def test_set_database_environment_creates_env_file(self):
        """Test set_database_environment creates .env file if it doesn't exist."""
        assert not os.path.exists(".env")

        set_database_environment("production")

        assert os.path.exists(".env")
        with open(".env", "r") as f:
            content = f.read()
        assert "DB_ENVIRONMENT=production" in content

    def test_set_database_environment_updates_existing_env_file(self):
        """Test set_database_environment updates existing .env file."""
        # Create initial .env file
        with open(".env", "w") as f:
            f.write("OTHER_VAR=value\nDB_ENVIRONMENT=local\nANOTHER_VAR=value2\n")

        set_database_environment("production")

        with open(".env", "r") as f:
            lines = f.readlines()

        # Check that other variables are preserved and DB_ENVIRONMENT is updated
        assert "OTHER_VAR=value\n" in lines
        assert "ANOTHER_VAR=value2\n" in lines
        assert "DB_ENVIRONMENT=production\n" in lines
        assert "DB_ENVIRONMENT=local\n" not in lines

    def test_set_database_environment_adds_to_existing_env_file(self):
        """Test set_database_environment adds DB_ENVIRONMENT to existing .env file."""
        # Create initial .env file without DB_ENVIRONMENT
        with open(".env", "w") as f:
            f.write("OTHER_VAR=value\nANOTHER_VAR=value2\n")

        set_database_environment("production")

        with open(".env", "r") as f:
            content = f.read()

        assert "OTHER_VAR=value" in content
        assert "ANOTHER_VAR=value2" in content
        assert "DB_ENVIRONMENT=production" in content

    def test_set_database_environment_updates_os_environ(self):
        """Test set_database_environment updates os.environ."""
        set_database_environment("production")
        assert os.environ["DB_ENVIRONMENT"] == "production"

        set_database_environment("local")
        assert os.environ["DB_ENVIRONMENT"] == "local"

    def test_set_database_environment_invalid_value_raises_error(self):
        """Test set_database_environment raises error for invalid values."""
        with pytest.raises(
            ValueError, match="Environment must be either 'local' or 'production'"
        ):
            set_database_environment("invalid")

    @patch("bluesky_summarizer.config.load_dotenv")
    def test_set_database_environment_reloads_dotenv(self, mock_load_dotenv):
        """Test set_database_environment reloads dotenv."""
        set_database_environment("production")
        mock_load_dotenv.assert_called_once_with(override=True)


class TestDatabaseFactory:
    """Test the database factory function."""

    def test_create_database_manager_local_environment(self):
        """Test create_database_manager returns DatabaseManager for local environment."""
        config = DatabaseConfig(
            db_path="./test.db",
            url="libsql://test.turso.io",
            auth_token="token123",
            environment="local",
        )

        manager = create_database_manager(config)
        assert isinstance(manager, DatabaseManager)

    @patch("bluesky_summarizer.database.factory.TursoDatabaseManager")
    def test_create_database_manager_production_environment(self, mock_turso_manager):
        """Test create_database_manager returns TursoDatabaseManager for production environment."""
        config = DatabaseConfig(
            db_path="./test.db",
            url="libsql://test.turso.io",
            auth_token="token123",
            environment="production",
        )

        create_database_manager(config)
        mock_turso_manager.assert_called_once_with("libsql://test.turso.io", "token123")

    def test_create_database_manager_production_without_url_raises_error(self):
        """Test create_database_manager raises error for production without URL."""
        config = DatabaseConfig(
            db_path="./test.db", url="", auth_token="token123", environment="production"
        )

        with pytest.raises(
            ValueError,
            match="Production database environment is configured but missing credentials",
        ):
            create_database_manager(config)

    def test_create_database_manager_production_without_token_raises_error(self):
        """Test create_database_manager raises error for production without token."""
        config = DatabaseConfig(
            db_path="./test.db",
            url="libsql://test.turso.io",
            auth_token="",
            environment="production",
        )

        with pytest.raises(
            ValueError,
            match="Production database environment is configured but missing credentials",
        ):
            create_database_manager(config)


class TestDatabaseManagerIntegration:
    """Integration tests for database managers with different environments."""

    def setup_method(self):
        """Set up for each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

    def teardown_method(self):
        """Clean up after each test method."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)

    def test_sqlite_database_manager_creation(self):
        """Test that SQLite database manager can be created and initialized."""
        config = DatabaseConfig(db_path="./test.db", environment="local")

        manager = create_database_manager(config)
        assert isinstance(manager, DatabaseManager)
        assert os.path.exists("./test.db")

    @patch("bluesky_summarizer.database.turso_operations.libsql")
    def test_turso_database_manager_creation(self, mock_libsql):
        """Test that Turso database manager can be created."""
        mock_client = MagicMock()
        mock_libsql.create_client.return_value = mock_client

        config = DatabaseConfig(
            db_path="./test.db",
            url="libsql://test.turso.io",
            auth_token="token123",
            environment="production",
        )

        manager = create_database_manager(config)
        assert isinstance(manager, TursoDatabaseManager)
        mock_libsql.create_client.assert_called_once_with(
            url="libsql://test.turso.io", auth_token="token123"
        )


class TestConfigIntegration:
    """Integration tests for config with database environment switching."""

    def setup_method(self):
        """Set up for each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        # Create a minimal .env file with required variables
        with open(".env", "w") as f:
            f.write("""
BLUESKY_HANDLE=test.bsky.social
BLUESKY_PASSWORD=test_password
ANTHROPIC_API_KEY=test_api_key
DB_ENVIRONMENT=local
DATABASE_PATH=./test.db
TURSO_DATABASE_URL=libsql://test.turso.io
TURSO_AUTH_TOKEN=test_token
""")

    def teardown_method(self):
        """Clean up after each test method."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)

    @patch("bluesky_summarizer.config.load_dotenv")
    def test_config_loads_local_environment(self, mock_load_dotenv):
        """Test that config correctly loads local environment settings."""
        os.environ.update(
            {
                "BLUESKY_HANDLE": "test.bsky.social",
                "BLUESKY_PASSWORD": "test_password",
                "ANTHROPIC_API_KEY": "test_api_key",
                "DB_ENVIRONMENT": "local",
                "DATABASE_PATH": "./test.db",
                "TURSO_DATABASE_URL": "libsql://test.turso.io",
                "TURSO_AUTH_TOKEN": "test_token",
            }
        )

        config = get_config()
        assert config.database.environment == "local"
        assert not config.database.is_turso
        assert config.database.path == "./test.db"

    @patch("bluesky_summarizer.config.load_dotenv")
    def test_config_loads_production_environment(self, mock_load_dotenv):
        """Test that config correctly loads production environment settings."""
        os.environ.update(
            {
                "BLUESKY_HANDLE": "test.bsky.social",
                "BLUESKY_PASSWORD": "test_password",
                "ANTHROPIC_API_KEY": "test_api_key",
                "DB_ENVIRONMENT": "production",
                "DATABASE_PATH": "./test.db",
                "TURSO_DATABASE_URL": "libsql://test.turso.io",
                "TURSO_AUTH_TOKEN": "test_token",
            }
        )

        config = get_config()
        assert config.database.environment == "production"
        assert config.database.is_turso
        assert config.database.url == "libsql://test.turso.io"
        assert config.database.auth_token == "test_token"

    @patch("bluesky_summarizer.config.load_dotenv")
    def test_environment_switching_updates_config_behavior(self, mock_load_dotenv):
        """Test that switching environments affects config behavior."""
        # Set up initial environment variables
        os.environ.update(
            {
                "BLUESKY_HANDLE": "test.bsky.social",
                "BLUESKY_PASSWORD": "test_password",
                "ANTHROPIC_API_KEY": "test_api_key",
                "DATABASE_PATH": "./test.db",
                "TURSO_DATABASE_URL": "libsql://test.turso.io",
                "TURSO_AUTH_TOKEN": "test_token",
            }
        )

        # Test local environment
        set_database_environment("local")
        config = get_config()
        assert config.database.environment == "local"
        assert not config.database.is_turso

        # Test production environment
        set_database_environment("production")
        config = get_config()
        assert config.database.environment == "production"
        assert config.database.is_turso


if __name__ == "__main__":
    pytest.main([__file__])
