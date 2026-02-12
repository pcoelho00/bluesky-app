#!/usr/bin/env python3
"""
Custom test runner for database environment functionality.
This bypasses pytest collection issues while testing all components.
"""

import os
import sys
import tempfile
import shutil

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Add src to path
sys.path.insert(0, "src")


def run_tests():
    """Run all database environment tests."""
    print("Running Database Environment Tests")
    print("=" * 50)

    # Test 1: DatabaseConfig functionality
    print("\nTesting DatabaseConfig...")
    try:
        from bluesky_summarizer.config import DatabaseConfig

        # Test default connection URL
        config = DatabaseConfig()
        assert config.connection_url == "sqlite:///./data/bluesky_feed.db"
        assert config.db_path == "./data/bluesky_feed.db"
        assert config.path == "./data/bluesky_feed.db"

        # Test custom connection URL
        config = DatabaseConfig(connection_url="sqlite:///./test.db")
        assert config.db_path == "./test.db"

        # Test non-SQLite URL returns URL as db_path
        config = DatabaseConfig(connection_url="postgresql://user:pw@host/db")
        assert config.db_path == "postgresql://user:pw@host/db"

        print("   DatabaseConfig tests passed")
    except Exception as e:
        print(f"   DatabaseConfig tests failed: {e}")
        return False

    # Test 2: Environment switching functions (legacy compat)
    print("\nTesting environment switching...")
    try:
        from bluesky_summarizer.config import (
            get_database_environment,
            set_database_environment,
        )

        # Create temporary directory for test
        temp_dir = tempfile.mkdtemp()
        original_cwd = os.getcwd()
        os.chdir(temp_dir)

        try:
            # Test setting and getting environment
            set_database_environment("local")
            assert get_database_environment() == "local", (
                "Should return local environment"
            )

            set_database_environment("production")
            assert get_database_environment() == "production", (
                "Should return production environment"
            )

            # Test .env file creation
            assert os.path.exists(".env"), ".env file should be created"

            with open(".env", "r") as f:
                content = f.read()
            assert "DB_ENVIRONMENT=production" in content, (
                ".env should contain production setting"
            )

            print("   Environment switching tests passed")
        finally:
            os.chdir(original_cwd)
            shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"   Environment switching tests failed: {e}")
        return False

    # Test 3: Database factory
    print("\nTesting database factory...")
    try:
        from bluesky_summarizer.database.factory import (
            create_database_manager,
            create_database_manager_from_path,
        )

        # Test creating from path
        temp_dir = tempfile.mkdtemp()
        try:
            db_path = os.path.join(temp_dir, "test_factory.db")
            manager = create_database_manager_from_path(db_path)
            assert manager is not None
            manager.close()
        finally:
            shutil.rmtree(temp_dir)

        print("   Database factory tests passed")
    except Exception as e:
        print(f"   Database factory tests failed: {e}")
        return False

    # Test 4: CLI functionality (basic import test)
    print("\nTesting CLI imports...")
    try:
        # Test that CLI functions can be imported
        import bluesky_summarizer.db_env_cli as db_env_cli

        assert hasattr(db_env_cli, "db_status"), "CLI should have db_status function"
        assert hasattr(db_env_cli, "show_db_status"), (
            "CLI should have show_db_status function"
        )

        print("   CLI import tests passed")
    except Exception as e:
        print(f"   CLI import tests failed: {e}")
        return False

    print("\nAll tests passed!")
    print("\nTest Summary:")
    print("   DatabaseConfig functionality")
    print("   Environment switching functions")
    print("   Database factory")
    print("   CLI imports")

    return True


if __name__ == "__main__":
    success = run_tests()

    if success:
        print("\n" + "=" * 50)
        print("Ready to use!")
        print("=" * 50)
        print("\nUse these commands to manage your database environment:")
        print("   python -m bluesky_summarizer.db_env_cli status  # Check current status")
    else:
        print("\nSome tests failed. Please check the implementation.")
        sys.exit(1)
