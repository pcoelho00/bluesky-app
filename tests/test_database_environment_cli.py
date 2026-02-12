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
from bluesky_summarizer.db_env_cli import db, db_status, show_db_status


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

    def test_db_status_command_sqlite(self):
        """Test db status command shows SQLite backend correctly."""
        # Create .env file with DATABASE_PATH
        with open(".env", "w") as f:
            f.write("DATABASE_PATH=./test.db\n")

        # Create test database file
        with open("./test.db", "w") as f:
            f.write("")

        result = self.runner.invoke(db_status)

        assert result.exit_code == 0
        assert "SQLite" in result.output
        assert "Database File" in result.output
        assert "Yes" in result.output

    def test_db_status_command_with_database_url(self):
        """Test db status command shows connection URL when DATABASE_URL is set."""
        with open(".env", "w") as f:
            f.write("DATABASE_URL=sqlite:///./my_app.db\n")

        with patch.dict(
            os.environ,
            {"DATABASE_URL": "sqlite:///./my_app.db"},
        ):
            result = self.runner.invoke(db_status)

        assert result.exit_code == 0
        assert "SQLite" in result.output
        assert "sqlite:///./my_app.db" in result.output

    def test_db_status_command_no_env_file(self):
        """Test db status command works when no .env file exists."""
        # Ensure no .env file and clear relevant env vars
        with patch.dict(os.environ, {}, clear=True):
            result = self.runner.invoke(db_status)

        assert result.exit_code == 0
        assert "Database Status" in result.output

    def test_db_help_command(self):
        """Test db help command shows available subcommands."""
        result = self.runner.invoke(db, ["--help"])

        assert result.exit_code == 0
        assert "Database environment management commands" in result.output
        assert "status" in result.output

    @patch("bluesky_summarizer.db_env_cli.console")
    def test_show_db_status_function_sqlite(self, mock_console):
        """Test show_db_status function with SQLite database."""
        with patch.dict(
            os.environ, {"DATABASE_PATH": "./test.db"}
        ):
            with open("./test.db", "w") as f:
                f.write("")

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

    def test_status_with_database_path(self):
        """Test status with DATABASE_PATH setting."""
        with open(".env", "w") as f:
            f.write("DATABASE_PATH=./test.db\n")

        with open("./test.db", "w") as f:
            f.write("")

        with patch.dict(
            os.environ,
            {"DATABASE_PATH": "./test.db"},
        ):
            result = self.runner.invoke(db_status)
            assert result.exit_code == 0
            assert "SQLite" in result.output

    def test_status_with_database_url(self):
        """Test status with DATABASE_URL taking precedence."""
        with open(".env", "w") as f:
            f.write(
                "DATABASE_URL=sqlite:///./custom.db\n"
                "DATABASE_PATH=./test.db\n"
            )

        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "sqlite:///./custom.db",
                "DATABASE_PATH": "./test.db",
            },
        ):
            result = self.runner.invoke(db_status)
            assert result.exit_code == 0
            assert "sqlite:///./custom.db" in result.output


if __name__ == "__main__":
    pytest.main([__file__])
