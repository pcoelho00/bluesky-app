"""
Tests for database environment CLI commands.
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch
from click.testing import CliRunner

# Import the standalone CLI functions
import sys

sys.path.append(".")
from bluesky_summarizer.db_env_cli import db, db_switch, db_status, show_db_status


class TestDatabaseEnvironmentCLI:
    """Test the database environment CLI commands."""

    def setup_method(self):
        """Set up for each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        self.runner = CliRunner()

    def teardown_method(self):
        """Clean up after each test method."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)

    def test_db_status_command_local_environment(self):
        """Test db status command shows local environment correctly."""
        # Create .env file with local environment
        with open(".env", "w") as f:
            f.write("DB_ENVIRONMENT=local\nDATABASE_PATH=./test.db\n")

        # Create test database file
        with open("./test.db", "w") as f:
            f.write("")

        result = self.runner.invoke(db_status)

        assert result.exit_code == 0
        assert "local (Local SQLite)" in result.output
        assert "Database Path" in result.output
        assert "✓ Yes" in result.output

    def test_db_status_command_production_environment(self):
        """Test db status command shows production environment correctly."""
        # Create .env file with production environment
        with open(".env", "w") as f:
            f.write("""
DB_ENVIRONMENT=production
TURSO_DATABASE_URL=libsql://test.turso.io
TURSO_AUTH_TOKEN=test_token
""")

        with patch.dict(
            os.environ,
            {
                "DB_ENVIRONMENT": "production",
                "TURSO_DATABASE_URL": "libsql://test.turso.io",
                "TURSO_AUTH_TOKEN": "test_token",
            },
        ):
            result = self.runner.invoke(db_status)

        assert result.exit_code == 0
        assert "production (Turso Cloud)" in result.output
        assert "Turso URL" in result.output
        assert "libsql://test.turso.io" in result.output

    def test_db_switch_to_local_command(self):
        """Test db switch to local command."""
        # Create .env file with production environment
        with open(".env", "w") as f:
            f.write("DB_ENVIRONMENT=production\n")

        with patch.dict(os.environ, {"DB_ENVIRONMENT": "production"}):
            result = self.runner.invoke(db_switch, ["local"])

        assert result.exit_code == 0
        assert "Switched to local database environment" in result.output

        # Check that .env file was updated
        with open(".env", "r") as f:
            content = f.read()
        assert "DB_ENVIRONMENT=local" in content

    def test_db_switch_to_production_command_with_credentials(self):
        """Test db switch to production command with valid credentials."""
        # Create .env file with local environment and Turso credentials
        with open(".env", "w") as f:
            f.write("""
DB_ENVIRONMENT=local
TURSO_DATABASE_URL=libsql://test.turso.io
TURSO_AUTH_TOKEN=test_token
""")

        with patch.dict(
            os.environ,
            {
                "DB_ENVIRONMENT": "local",
                "TURSO_DATABASE_URL": "libsql://test.turso.io",
                "TURSO_AUTH_TOKEN": "test_token",
            },
        ):
            result = self.runner.invoke(db_switch, ["production"])

        assert result.exit_code == 0
        assert "Switched to production database environment" in result.output

        # Check that .env file was updated
        with open(".env", "r") as f:
            content = f.read()
        assert "DB_ENVIRONMENT=production" in content

    def test_db_switch_to_production_command_without_credentials(self):
        """Test db switch to production command without valid credentials."""
        # Create .env file with local environment but no Turso credentials
        with open(".env", "w") as f:
            f.write("DB_ENVIRONMENT=local\n")

        with patch.dict(os.environ, {"DB_ENVIRONMENT": "local"}, clear=True):
            result = self.runner.invoke(db_switch, ["production"])

        assert result.exit_code == 1
        assert "Production environment requires TURSO_DATABASE_URL" in result.output

    def test_db_switch_same_environment(self):
        """Test db switch to same environment shows appropriate message."""
        # Create .env file with local environment
        with open(".env", "w") as f:
            f.write("DB_ENVIRONMENT=local\n")

        with patch.dict(os.environ, {"DB_ENVIRONMENT": "local"}):
            result = self.runner.invoke(db_switch, ["local"])

        assert result.exit_code == 0
        assert "Already using local database environment" in result.output

    def test_db_switch_invalid_environment(self):
        """Test db switch with invalid environment shows error."""
        result = self.runner.invoke(db_switch, ["invalid"])

        # Click should handle the invalid choice and show usage
        assert result.exit_code != 0

    def test_db_help_command(self):
        """Test db help command shows available subcommands."""
        result = self.runner.invoke(db, ["--help"])

        assert result.exit_code == 0
        assert "Database environment management commands" in result.output
        assert "status" in result.output
        assert "switch" in result.output

    def test_db_switch_help_command(self):
        """Test db switch help command shows usage."""
        result = self.runner.invoke(db_switch, ["--help"])

        assert result.exit_code == 0
        assert (
            "Switch between local and production database environments" in result.output
        )
        assert "local" in result.output
        assert "production" in result.output

    @patch("db_env_cli.console")
    def test_show_db_status_function_local(self, mock_console):
        """Test show_db_status function with local environment."""
        with patch.dict(
            os.environ, {"DB_ENVIRONMENT": "local", "DATABASE_PATH": "./test.db"}
        ):
            with open("./test.db", "w") as f:
                f.write("")

            show_db_status()

            # Check that console.print was called with a table
            mock_console.print.assert_called_once()
            args = mock_console.print.call_args[0]
            assert len(args) == 1  # Should be called with one argument (the table)

    @patch("db_env_cli.console")
    def test_show_db_status_function_production(self, mock_console):
        """Test show_db_status function with production environment."""
        with patch.dict(
            os.environ,
            {
                "DB_ENVIRONMENT": "production",
                "TURSO_DATABASE_URL": "libsql://test.turso.io",
                "TURSO_AUTH_TOKEN": "test_token",
            },
        ):
            show_db_status()

            # Check that console.print was called with a table
            mock_console.print.assert_called_once()
            args = mock_console.print.call_args[0]
            assert len(args) == 1  # Should be called with one argument (the table)


class TestDatabaseEnvironmentCLIIntegration:
    """Integration tests for the database environment CLI."""

    def setup_method(self):
        """Set up for each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        self.runner = CliRunner()

    def teardown_method(self):
        """Clean up after each test method."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)

    def test_full_workflow_local_to_production_and_back(self):
        """Test full workflow of switching between environments."""
        # Create .env file with all needed variables
        with open(".env", "w") as f:
            f.write("""
DB_ENVIRONMENT=local
DATABASE_PATH=./test.db
TURSO_DATABASE_URL=libsql://test.turso.io
TURSO_AUTH_TOKEN=test_token
""")

        # Create test database file
        with open("./test.db", "w") as f:
            f.write("")

        # Test initial status (local)
        with patch.dict(
            os.environ,
            {
                "DB_ENVIRONMENT": "local",
                "DATABASE_PATH": "./test.db",
                "TURSO_DATABASE_URL": "libsql://test.turso.io",
                "TURSO_AUTH_TOKEN": "test_token",
            },
        ):
            result = self.runner.invoke(db_status)
            assert result.exit_code == 0
            assert "local (Local SQLite)" in result.output

        # Switch to production
        with patch.dict(
            os.environ,
            {
                "DB_ENVIRONMENT": "local",
                "DATABASE_PATH": "./test.db",
                "TURSO_DATABASE_URL": "libsql://test.turso.io",
                "TURSO_AUTH_TOKEN": "test_token",
            },
        ):
            result = self.runner.invoke(db_switch, ["production"])
            assert result.exit_code == 0
            assert "Switched to production database environment" in result.output

        # Verify .env file was updated
        with open(".env", "r") as f:
            content = f.read()
        assert "DB_ENVIRONMENT=production" in content

        # Switch back to local
        with patch.dict(
            os.environ,
            {
                "DB_ENVIRONMENT": "production",
                "DATABASE_PATH": "./test.db",
                "TURSO_DATABASE_URL": "libsql://test.turso.io",
                "TURSO_AUTH_TOKEN": "test_token",
            },
        ):
            result = self.runner.invoke(db_switch, ["local"])
            assert result.exit_code == 0
            assert "Switched to local database environment" in result.output

        # Verify .env file was updated back
        with open(".env", "r") as f:
            content = f.read()
        assert "DB_ENVIRONMENT=local" in content

    def test_env_file_preservation(self):
        """Test that .env file preserves other variables during switches."""
        # Create .env file with multiple variables
        initial_content = """
# Bluesky credentials
BLUESKY_HANDLE=test.bsky.social
BLUESKY_PASSWORD=test_password

# API keys
ANTHROPIC_API_KEY=test_api_key

# Database settings
DB_ENVIRONMENT=local
DATABASE_PATH=./test.db
TURSO_DATABASE_URL=libsql://test.turso.io
TURSO_AUTH_TOKEN=test_token

# Other settings
SOME_OTHER_VAR=value123
"""
        with open(".env", "w") as f:
            f.write(initial_content)

        # Switch environment
        with patch.dict(
            os.environ,
            {
                "DB_ENVIRONMENT": "local",
                "TURSO_DATABASE_URL": "libsql://test.turso.io",
                "TURSO_AUTH_TOKEN": "test_token",
            },
        ):
            result = self.runner.invoke(db_switch, ["production"])
            assert result.exit_code == 0

        # Check that all other variables are preserved
        with open(".env", "r") as f:
            final_content = f.read()

        assert "BLUESKY_HANDLE=test.bsky.social" in final_content
        assert "BLUESKY_PASSWORD=test_password" in final_content
        assert "ANTHROPIC_API_KEY=test_api_key" in final_content
        assert "DATABASE_PATH=./test.db" in final_content
        assert "TURSO_DATABASE_URL=libsql://test.turso.io" in final_content
        assert "TURSO_AUTH_TOKEN=test_token" in final_content
        assert "SOME_OTHER_VAR=value123" in final_content
        assert "DB_ENVIRONMENT=production" in final_content
        assert "DB_ENVIRONMENT=local" not in final_content


if __name__ == "__main__":
    pytest.main([__file__])
